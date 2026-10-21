<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
function mysql_query_time() {
    $numargs = func_num_args();
    $sql = func_get_arg(0);
    $connect_mysql = func_get_arg(1);
    $time = microtime(true);
    $sth = mysql_query($sql, $connect_mysql);
    echo (('Time:' . (microtime(true) - $time)) . 's
');
    return $sth;
    
}
