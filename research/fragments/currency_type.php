<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
function currency_type($currency, $CurTypeID, $text_key) {
    if ((($CurTypeID[$text_key] == 0) || ($CurTypeID[$text_key] == ''))) {
        $currency_type = '-?-';
    } else {
        $currency_type = $currency[$CurTypeID[$text_key]]['cur_type'];
    }
    return $currency_type;
    
}
