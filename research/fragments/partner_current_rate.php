<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
function partner_current_rate($programm, $field) {
    global $connect_mysql;
    global $pr_partner;
    global $bn_partner;
    global $count_sign_partner;
    global $currency_save;
    global $CurTypeID_save;
    if (($programm == 'buying')) {
        if (($field == 'name')) {
            $string = 'Текущий процент по этой партнерской программе:';
        } else {
            if (($field == 'value')) {
                $string = (('&nbsp;' . $pr_partner) . ' %');
            }
        }
    } else {
        if (($programm == 'inputs')) {
            if (($field == 'name')) {
                $string = 'Текущий бонус по этой партнерской программе:';
            } else {
                if (($field == 'value')) {
                    $string = round($bn_partner, $count_sign_partner);
                }
            }
        }
    }
    return $string;
    
}
