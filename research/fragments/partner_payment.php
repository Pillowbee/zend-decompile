<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
function partner_payment($id_partner, $status_payment, $programm) {
    $_zend_decompiler_pc_v19 = 'B000';
    while (1) {
        switch ($_zend_decompiler_pc_v19) {
            case 'B000':
                global $connect_mysql;
                global $count_sign_partner;
                if (($programm == 'buying')) {
                    $_zend_decompiler_pc_v19 = 'B009';
                } else {
                    $_zend_decompiler_pc_v19 = 'B015';
                }
                break;
            case 'B009':
                $sql = 'SELECT sum(sum_all/100*pr_partner)
 FROM partner_percent pp
 LEFT JOIN `orders` o ON pp.id_orders = o.id_orders
 WHERE id_partner =  \'' . $id_partner . '\' AND status_id = \'4\'';
                $_zend_decompiler_pc_v19 = 'B024';
                break;
            case 'B015':
                if (($programm == 'inputs')) {
                    $_zend_decompiler_pc_v19 = 'B017';
                } else {
                    $_zend_decompiler_pc_v19 = 'B023';
                }
                break;
            case 'B017':
                $sql = 'SELECT round(sum(count_host*bn_partner), 4) FROM partner_bonus WHERE id_partner = \'' . $id_partner . '\' ';
                $_zend_decompiler_pc_v19 = 'B024';
                break;
            case 'B023':
                return NULL;
            case 'B024':
                if (($status_payment == 'оплачено')) {
                    $_zend_decompiler_pc_v19 = 'B026';
                } else {
                    $_zend_decompiler_pc_v19 = 'B029';
                }
                break;
            case 'B026':
                $sql_1 = ($sql . 'AND `date_payment` != \'0000-00-00 00:00:00\' GROUP BY id_partner');
                $_zend_decompiler_pc_v19 = 'B033';
                break;
            case 'B029':
                if (($status_payment == 'долг')) {
                    $_zend_decompiler_pc_v19 = 'B031';
                } else {
                    $_zend_decompiler_pc_v19 = 'B033';
                }
                break;
            case 'B031':
                $sql_1 = ($sql . 'AND `date_payment` = \'0000-00-00 00:00:00\' GROUP BY id_partner');
                $_zend_decompiler_pc_v19 = 'B033';
                break;
            case 'B033':
                $sth = mysql_query($sql_1);
                $hash_ref = mysql_fetch_row($sth);
                if (($hash_ref[0] == '')) {
                    $_zend_decompiler_pc_v19 = 'B046';
                } else {
                    $_zend_decompiler_pc_v19 = 'B048';
                }
                break;
            case 'B046':
                $hash_ref[0] = 0;
                $_zend_decompiler_pc_v19 = 'B048';
                break;
            case 'B048':
                return round($hash_ref[0], $count_sign_partner);
            default:
                trigger_error('Invalid recovered control-flow state', E_USER_ERROR);
                return NULL;
        }
    }
}
