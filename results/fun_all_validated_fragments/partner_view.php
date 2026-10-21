<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
function partner_view($name_set) {
    global $connect_mysql;
    $sql = 'SELECT value_set FROM setup WHERE name_set = \'' . $name_set . '\'';
    $sth = mysql_query($sql, $connect_mysql);
    $row = mysql_fetch_assoc($sth);
    if (($row['value_set'] != '0')) {
        return $row['value_set'];
    } else {
        return NULL;
    }
    
}
