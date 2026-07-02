/**
 * MDB clear table helper - marks all rows in a table as deleted.
 * Uses brute-force page scanning since JET4 usage maps (type 4) are
 * not supported by mdbtools.
 *
 * Usage: mdb_clear_table <mdb_path> <table_name>
 *
 * Example: mdb_clear_table data.mdb Q_Inputsd
 */
#define _FILE_OFFSET_BITS 64
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <glib.h>
#include <mdbtools.h>

int main(int argc, char *argv[]) {
    MdbHandle *mdb;
    MdbTableDef *table;
    int rco, row_count, row, pg_size;

    if (argc != 3) {
        fprintf(stderr, "Usage: %s <mdb_path> <table_name>\n", argv[0]);
        return 1;
    }

    mdb = mdb_open(argv[1], MDB_WRITABLE);
    if (!mdb) return 1;

    mdb_set_bind_size(mdb, 16384);
    mdb_init_backends(mdb);
    mdb_set_default_backend(mdb, "access");

    mdb_read_catalog(mdb, MDB_TABLE);
    table = mdb_read_table_by_name(mdb, argv[2], MDB_TABLE);
    if (!table) { mdb_close(mdb); return 1; }

    mdb_read_columns(table);
    mdb_read_indices(table);

    rco = mdb->fmt->row_count_offset;
    pg_size = mdb->fmt->pg_size;
    guint32 tbl_pg = table->entry->table_pg;

    FILE *f = fopen(argv[1], "r+b");
    if (!f) { mdb_free_tabledef(table); mdb_close(mdb); return 1; }

    /* Find end of file */
    fseeko(f, 0, SEEK_END);
    long file_size = ftello(f);
    int total_pages = file_size / pg_size;

    int cleared = 0;

    for (int pg = 0; pg < total_pages; pg++) {
        unsigned char buf[8];
        fseeko(f, (off_t)pg * pg_size, SEEK_SET);
        if (fread(buf, 1, 8, f) != 8) break;
        /* Data page: type 0x0101 at offset 0, table_pg backpointer at offset 4 */
        if (buf[0] == 0x01 && buf[1] == 0x01) {
            guint32 bpt = mdb_get_int32(buf, 4);
            if (bpt == tbl_pg) {
                unsigned char page_buf[pg_size];
                fseeko(f, (off_t)pg * pg_size, SEEK_SET);
                if (fread(page_buf, 1, pg_size, f) != (size_t)pg_size) break;

                row_count = mdb_get_int16(page_buf, rco);
                for (row = 0; row < row_count; row++) {
                    int off = rco + 2 + row * 2;
                    int val = mdb_get_int16(page_buf, off);
                    val |= 0x4000;
                    mdb_put_int16(page_buf, off, val);
                }

                fprintf(stderr, "  page %d: %d rows, row0 entry=0x%04x\n",
                    pg, row_count,
                    row_count>0 ? mdb_get_int16(page_buf, rco+2) : 0);
                fseeko(f, (off_t)pg * pg_size, SEEK_SET);
                fwrite(page_buf, 1, pg_size, f);
                cleared++;
            }
        }
    }

    fflush(f);
    fclose(f);
    mdb_free_tabledef(table);
    mdb_close(mdb);
    fprintf(stderr, "Cleared %d pages\n", cleared);
    return 0;
}
