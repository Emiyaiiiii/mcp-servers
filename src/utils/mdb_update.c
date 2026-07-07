/**
 * MDB update helper - uses mdbtools library to update a value in an MDB table.
 * Directly modifies the raw row data on the page to avoid encoding issues.
 *
 * Usage: mdb_update <mdb_path> <table_name> <column_name> <new_value> <key_column> <key_value>
 *
 * Example: mdb_update data.mdb Dispatch_Par Control_Par 2500 stcd 23
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <glib.h>
#include <mdbtools.h>

int mdb_update_indexes(MdbTableDef *table, int num_fields, MdbField *fields, guint32 pgnum, guint16 rownum);
ssize_t mdb_write_pg(MdbHandle *mdb, unsigned long pg);

int main(int argc, char *argv[]) {
    MdbHandle *mdb;
    MdbTableDef *table;
    int i, num_fields;
    int col_idx = -1;
    int key_col_idx = -1;
    int key_val;
    double new_val;
    int found = 0;
    int row_num = 0;
    char **bind_buffers;

    if (argc != 7) {
        fprintf(stderr, "Usage: %s <mdb_path> <table_name> <column_name> <new_value> <key_column> <key_value>\n", argv[0]);
        return 1;
    }

    char *mdb_path = argv[1];
    char *table_name = argv[2];
    char *col_name = argv[3];
    new_val = atof(argv[4]);
    char *key_col = argv[5];
    key_val = atoi(argv[6]);

    mdb = mdb_open(mdb_path, MDB_WRITABLE);
    if (!mdb) {
        fprintf(stderr, "Failed to open MDB file: %s\n", mdb_path);
        return 1;
    }

    mdb_set_bind_size(mdb, 16384);
    mdb_init_backends(mdb);
    mdb_set_default_backend(mdb, "access");

    mdb_read_catalog(mdb, MDB_TABLE);
    table = mdb_read_table_by_name(mdb, table_name, MDB_TABLE);
    if (!table) {
        fprintf(stderr, "Table '%s' not found\n", table_name);
        mdb_close(mdb);
        return 1;
    }

    mdb_read_columns(table);
    mdb_read_indices(table);

    /* Find column indices */
    for (i = 0; i < table->num_cols; i++) {
        MdbColumn *col = g_ptr_array_index(table->columns, i);
        if (g_ascii_strcasecmp(col->name, col_name) == 0) col_idx = i;
        if (g_ascii_strcasecmp(col->name, key_col) == 0) key_col_idx = i;
    }

    if (col_idx == -1 || key_col_idx == -1) {
        fprintf(stderr, "Column not found\n");
        mdb_free_tabledef(table);
        mdb_close(mdb);
        return 1;
    }

    /* Bind columns and find matching row */
    num_fields = table->num_cols;
    bind_buffers = calloc(num_fields, sizeof(char *));
    for (i = 0; i < num_fields; i++) {
        bind_buffers[i] = g_malloc(16384);
        mdb_bind_column(table, i + 1, bind_buffers[i], NULL);
    }

    mdb_rewind_table(table);
    while (mdb_fetch_row(table)) {
        if (atoi(bind_buffers[key_col_idx]) == key_val) {
            found = 1;
            break;
        }
        row_num++;
    }

    if (!found) {
        fprintf(stderr, "Row not found\n");
        for (i = 0; i < num_fields; i++) g_free(bind_buffers[i]);
        free(bind_buffers);
        mdb_free_tabledef(table);
        mdb_close(mdb);
        return 1;
    }

    /* Now we need to modify the raw row data on the page.
     * The current page is in mdb->pg_buf.
     * We need to find the row on this page and modify Control_Par bytes.
     */

    /* Get the row start offset from the row offset table.
     * After mdb_fetch_row returns, table->cur_row has been incremented,
     * so the row we found is at table->cur_row - 1 on the current page.
     */
    int rco = mdb->fmt->row_count_offset;
    int row_on_page = table->cur_row - 1;
    int row_start = mdb_get_int16(mdb->pg_buf, rco + 2 + row_on_page * 2) & 0x1fff;
    int row_end;
    if (row_on_page == 0) {
        row_end = mdb->fmt->pg_size;
    } else {
        row_end = mdb_get_int16(mdb->pg_buf, rco + row_on_page * 2) & 0x1fff;
    }

    /* Get the Control_Par column info to find its offset in the row */
    MdbColumn *target_col = g_ptr_array_index(table->columns, col_idx);

    /* The Control_Par is a Single (float), which is a fixed-length column.
     * Fixed columns are packed first in the row, after the column count byte(s).
     * The offset within fixed columns is target_col->fixed_offset.
     * For Jet4: column count is 2 bytes.
     */
    int col_count_size = IS_JET3(mdb) ? 1 : 2;
    int data_offset = row_start + col_count_size + target_col->fixed_offset;

    /* Write the new float value directly into the page buffer */
    float fval = (float)new_val;
    memcpy(mdb->pg_buf + data_offset, &fval, 4);

    /* Write the modified page back to disk */
    mdb_write_pg(mdb, table->cur_phys_pg);

    /* Cleanup */
    for (i = 0; i < num_fields; i++) g_free(bind_buffers[i]);
    free(bind_buffers);
    mdb_free_tabledef(table);
    mdb_close(mdb);

    fprintf(stderr, "Updated successfully: %s=%d, %s=%g\n", key_col, key_val, col_name, new_val);
    return 0;
}
