<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
function news_name_out($id_section) {
    global $connect_mysql;
    $sql = 'SELECT name_section FROM news_section WHERE id_section = \'' . $id_section . '\' AND visibility = 1';
    $sth = mysql_query($sql, $connect_mysql);
    $hash_ref = mysql_fetch_row($sth);
    $name_section = $hash_ref[0];
    return $name_section;
    
}
