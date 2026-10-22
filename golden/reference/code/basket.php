<?php
/* EXPERIMENTAL Zend recovery v29. Verify before use. */
$basket_ch = 0;
if (($id_wares_buy[0] != '')) {
    $n = 0;
    while ($id_wares_buy[$n] != '') {
        $qty = $amount_buy[$n];
        $id = $id_wares_buy[$n];
        if (($qty != '0')) {
            $ware = array('', '');
            if (strstr($order, $id . '.')) {
                $ar = explode(':', $order);
                $i = 0;
                while ($i < count($ar)) {
                    $ware = explode('.', $ar[$i]);
                    if (($id == $ware[0])) {
                        $newqty = sprintf('%d', ($ware[1] + $qty));
                        $ar[$i] = ($ware[0] . '.' . $newqty);
                    }
                    ++$i;
                }
                $order = join(':', $ar);
            } else {
                if ((0 < strlen($order))) {
                    $order .= ':';
                }
                $order .= $id_wares_buy[$n] . '.' . $qty;
            }
        }
        ++$n;
    }
    setcookie('order', $order, 0, '/');
    $basket_ch = 1;
}
if (($p_id != '')) {
    $order_del = $order;
    $order = '';
    setcookie('order', $order, 0, '/');
}
if (($id_del != '')) {
    $ar = explode(':', $order);
    $i = 0;
    while ($i < count($ar)) {
        $ware = explode('.', $ar[$i]);
        if (($id_del != $ware[0])) {
            $res[] = $ar[$i];
        }
        ++$i;
    }
    if ((0 < count($res))) {
        $order = join(':', $res);
    } else {
        $order = '';
    }
    setcookie('order', $order, 0, '/');
    $id_del = '';
}
if (($id_change != '')) {
    if ((0 < $qty)) {
        $ar = explode(':', $order);
        $i = 0;
        while ($i < count($ar)) {
            $ware = explode('.', $ar[$i]);
            if (($id_change == $ware[0])) {
                $newqty = sprintf('%d', ($ware[1] + $qty));
                $ar[$i] = ($ware[0] . '.' . $qty);
            }
            ++$i;
        }
        $order = join(':', $ar);
        setcookie('order', $order, 0, '/');
    }
}
$id_groups_temp = $id_groups;
return 1;


function course_basket() {
    global $connect_mysql;
    global $CurTypeID;
    global $currency;
    if (($CurTypeID['national'] != $CurTypeID['user'])) {
        if (($currency[$CurTypeID['user']]['position'] == 1)) {
            $course = ($currency[$CurTypeID['user']]['cur_type'] . '1');
        } else {
            $course = ('1 ' . $currency[$CurTypeID['user']]['cur_type']);
        }
        $string_basket = ((($course . ' нал. = ' . course_out('cur_rate_nal')) . ' &nbsp; ' . $course . ' безнал. = ') . course_out('cur_rate_bnal'));
    } else {
        $string_basket = '&nbsp;';
    }
    return $string_basket;
    
}
