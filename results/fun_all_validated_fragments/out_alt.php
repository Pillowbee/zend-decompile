<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
function out_alt() {
    global $connect_mysql;
    global $out_name_title;
    $out_name_title = ltrim($out_name_title);
    return $out_name_title;
    
}
