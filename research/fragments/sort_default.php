<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
function sort_default($id_sort) {
    global $connect_mysql;
    $sql = 'SELECT name_col_def, direction_sort FROM sort_default WHERE id_sort = \'' . $id_sort . '\'';
    $sth = mysql_query($sql, $connect_mysql);
    $hash_ref = mysql_fetch_row($sth);
    $name_col_def = $hash_ref[0];
    $direction_sort = $hash_ref[1];
    $string_order = (($name_col_def . ' ') . $direction_sort);
    if (($name_col_def == '')) {
        $string_order = '\'\'';
    }
    return $string_order;
    
}
