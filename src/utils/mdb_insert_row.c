/**
 * MDB insert row - inserts rows into an MDB table by rewriting existing data pages
 * with larger row slots. Since JET4 usage maps (type 4) can't be updated via
 * mdbtools, we reuse existing pages that are already in the usage map.
 */
#define _FILE_OFFSET_BITS 64
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>
#include <glib.h>
#include <mdbtools.h>

static double dt_parse(const char *s) {
    struct tm tm={0};int y,M,d,h,m,sec;
    if(sscanf(s,"%d-%d-%d %d:%d:%d",&y,&M,&d,&h,&m,&sec)>=3){
        tm.tm_year=y-1900;tm.tm_mon=M-1;tm.tm_mday=d;
        tm.tm_hour=h;tm.tm_min=m;tm.tm_sec=sec;tm.tm_isdst=0;
        return (double)timegm(&tm)/86400.0+25569.0;
    }return 0.0;
}

int main(int argc,char*argv[]){
    if(argc!=3)return 1;

    char**rows=malloc(65536*sizeof(char*));int nrows=0;char line[65536];
    while(fgets(line,sizeof(line),stdin)){
        size_t l=strlen(line);
        while(l>0&&(line[l-1]=='\n'||line[l-1]=='\r'))line[--l]=0;
        if(!l)continue;
        rows[nrows]=strdup(line);if(++nrows>=65536)break;
    }
    if(!nrows){free(rows);return 0;}

    MdbHandle*mdb=mdb_open(argv[1],MDB_WRITABLE);
    if(!mdb){fprintf(stderr,"Failed to open MDB\n");return 1;}
    mdb_set_bind_size(mdb,16384);mdb_init_backends(mdb);
    mdb_set_default_backend(mdb,"access");
    mdb_read_catalog(mdb,MDB_TABLE);
    MdbTableDef*table=mdb_read_table_by_name(mdb,argv[2],MDB_TABLE);
    if(!table){fprintf(stderr,"Table not found\n");mdb_close(mdb);return 1;}
    mdb_read_columns(table);mdb_read_indices(table);

    int nc=table->num_cols,pg_size=mdb->fmt->pg_size,rco=mdb->fmt->row_count_offset;
    guint32 tbl_pg=table->entry->table_pg;
    int inserted=0,ri=0;

    FILE*f=fopen(argv[1],"r+b");
    if(!f){mdb_close(mdb);return 1;}

    /* Find existing data pages */
    fseeko(f,0,SEEK_END);
    long file_size=ftello(f);
    int total_pages=file_size/pg_size;
    guint32 data_pages[65536];
    int ndp=0;

    for(int pg=0;pg<total_pages;pg++){
        unsigned char buf[8];
        fseeko(f,(off_t)pg*pg_size,SEEK_SET);
        if(fread(buf,1,8,f)!=8)break;
        if(buf[0]==0x01&&buf[1]==0x01){
            guint32 bpt=mdb_get_int32(buf,4);
            if(bpt==tbl_pg){
                data_pages[ndp++]=pg;
                if(ndp>=65536)break;
            }
        }
    }
    if(ndp==0){fprintf(stderr,"No existing data pages\n");fclose(f);mdb_close(mdb);return 1;}

    /* Pre-pack all rows */
    unsigned char *packed=malloc(nrows*pg_size);
    int *psizes=malloc(nrows*sizeof(int));
    for(int i=0;i<nrows;i++){
        char*vals[64];int nv=0;
        char*p=rows[i];
        while(p&&nv<64){vals[nv++]=p;p=strchr(p,'\t');if(p)*p++='\0';}
        if(nv>nc)nv=nc;

        MdbField*fields=calloc(nc,sizeof(MdbField));
        for(int c=0;c<nv;c++){
            MdbColumn*col=g_ptr_array_index(table->columns,c);
            fields[c].colnum=c;fields[c].is_fixed=col->is_fixed;
            if(!vals[c]||!strlen(vals[c])){fields[c].is_null=1;continue;}
            fields[c].is_null=0;
            if(col->col_type==MDB_TEXT||col->col_type==MDB_MEMO){
                GError*err=NULL;gsize bw;
                gchar*utf16=g_convert(vals[c],-1,"UTF-16LE","UTF-8",NULL,&bw,&err);
                if(!utf16)continue;
                fields[c].value=g_malloc(bw);memcpy(fields[c].value,utf16,bw);fields[c].siz=bw;
                g_free(utf16);
            }else if(col->col_type==MDB_DATETIME){
                double d=dt_parse(vals[c]);fields[c].value=g_malloc(8);memcpy(fields[c].value,&d,8);fields[c].siz=8;
            }else if(col->col_type==MDB_FLOAT){
                float fv=(float)atof(vals[c]);fields[c].value=g_malloc(4);memcpy(fields[c].value,&fv,4);fields[c].siz=4;
            }else if(col->col_type==MDB_DOUBLE){
                double dv=atof(vals[c]);fields[c].value=g_malloc(8);memcpy(fields[c].value,&dv,8);fields[c].siz=8;
            }else if(col->col_type==MDB_LONGINT){
                int iv=atoi(vals[c]);fields[c].value=g_malloc(4);mdb_put_int32(fields[c].value,0,iv);fields[c].siz=4;
            }else if(col->col_type==MDB_INT){
                short sv=(short)atoi(vals[c]);fields[c].value=g_malloc(2);mdb_put_int16(fields[c].value,0,sv);fields[c].siz=2;
            }
        }

        memset(packed+i*pg_size,0,pg_size);
        psizes[i]=mdb_pack_row(table,packed+i*pg_size,nv,fields);
        for(int c=0;c<nv;c++)if(fields[c].value)g_free(fields[c].value);
        free(fields);
    }

    /* Determine rows per page */
    int max_psize=0;
    for(int i=0;i<nrows;i++)if(psizes[i]>max_psize)max_psize=psizes[i];
    int entry_overhead=2;
    int rows_per_page=(pg_size-rco-2-entry_overhead)/(max_psize+entry_overhead);
    if(rows_per_page<1)rows_per_page=1;

    fprintf(stderr,"max_psize=%d rows_per_page=%d\n", max_psize, rows_per_page);

    /* Rewrite existing pages */
    for(int pi=0;pi<ndp&&ri<nrows;pi++){
        unsigned char page_buf[pg_size];
        memset(page_buf,0,sizeof(page_buf));

        /* Page header */
        page_buf[0]=0x01;page_buf[1]=0x01;
        mdb_put_int32(page_buf,4,tbl_pg);

        int nthis=nrows-ri;
        if(nthis>rows_per_page)nthis=rows_per_page;
        if(nthis<=0)break; /* no more rows to insert */

        /* Pack rows from bottom of page upward.
         * Row 0 goes at the BOTTOM (highest offset, closest to pg_size).
         * Entry0 (at rco+2) MUST be > Entry1 (at rco+4).
         * mdb_find_row expects:
         *   row 0: start=entry0, end=pg_size
         *   row 1: start=entry1, end=entry0
         * So entry0 must be the bottommost row's start.
         */
        int bottom = pg_size;
        for(int r=0;r<nthis;r++){
            int row_start = bottom - psizes[ri+r];
            memcpy(page_buf+row_start, packed+(ri+r)*pg_size, psizes[ri+r]);
            mdb_put_int16(page_buf, rco+2+r*2, row_start);
            bottom = row_start;
        }

        /* Check if data fits */
        int total_data = 0;
        for(int r=0;r<nthis;r++)total_data+=psizes[ri+r];
        int header_size = rco + 2 + nthis*2 + 2; /* count + entries + end marker */
        if(header_size + total_data > pg_size){
            fprintf(stderr,"  page %d: need %d bytes, have %d, skipping\n",
                data_pages[pi], header_size+total_data, pg_size);
            break;
        }

        /* End marker = pg_size (used as boundary for mdb_find_row row 0) */
        mdb_put_int16(page_buf, rco+2+nthis*2, pg_size);

        /* Row count */
        mdb_put_int16(page_buf, rco, nthis);

        /* Write page */
        fseeko(f,(off_t)data_pages[pi]*pg_size,SEEK_SET);
        fwrite(page_buf,1,pg_size,f);
        fflush(f);

        ri+=nthis;
        inserted+=nthis;
    }

    free(packed);free(psizes);
    fclose(f);mdb_close(mdb);

    fprintf(stderr,"Inserted %d/%d rows (%d pages)\n",inserted,nrows,ri>0?(ri+rows_per_page-1)/rows_per_page:0);
    for(int i=0;i<nrows;i++)free(rows[i]);
    free(rows);
    return 0;
}
