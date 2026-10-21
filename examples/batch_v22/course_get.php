<?php
/* EXPERIMENTAL Zend recovery v22. Verify before use. */
$CurTypeID = array();
$CurTypeID['national'] = $CurTypeID_national;
$CurTypeID['basket'] = $CurTypeID_basket;
$CurTypeID['user'] = $CurTypeID_user;
$CurTypeID['admin'] = $CurTypeID_admin;
$sql1 = 'SELECT  id, cur_ticker, cur_type, cur_rate_nal, cur_rate_bnal, descriptions, position
 FROM currency WHERE visibility = \'1\' ORDER BY sorting';
$sth1 = mysql_query($sql1);
while ($hash_ref = mysql_fetch_assoc($sth1)) {
    $currency[$hash_ref['id']] = $hash_ref;
}
return 1;


function course_out($cur_rate) {
    global $connect_mysql;
    global $CurTypeID;
    global $currency;
    if (($currency[$CurTypeID['national']]['position'] == 1)) {
        $string_cur_rate = ($currency[$CurTypeID['national']]['cur_type'] . $currency[$CurTypeID['user']][$cur_rate]);
    } else {
        $string_cur_rate = (($currency[$CurTypeID['user']][$cur_rate] . ' ') . $currency[$CurTypeID['national']]['cur_type']);
    }
    return $string_cur_rate;
    
}
