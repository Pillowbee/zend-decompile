<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
function url_prefix() {
    global $connect_mysql;
    global $old_search;
    global $id_auth_page;
    $numargs = func_num_args();
    if (($old_search == 'y')) {
        if (($numargs != 0)) {
            return '';
        } else {
            return '/';
        }
    } else {
        if (($id_auth_page == 1)) {
            return '../';
        } else {
            return '';
        }
    }
    
}
