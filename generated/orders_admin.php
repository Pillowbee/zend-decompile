<?php
/* EXPERIMENTAL Zend recovery v19. Verify before use. */
check_database($key, $key1, $connect_mysql, $db_name);
if ((right_set_admin($REMOTE_USER, 'orders_admin') == 0)) {
    include 'include/rights_txt/viewing_pages.php';
    return NULL;
} else {
    $id_orders = $HTTP_GET_VARS['id_orders'];
    if (($id_orders == '')) {
        $id_orders = $HTTP_POST_VARS['id_orders'];
    }
    $sum_all = 0;
    $update_sum_all = '';
    $error_new_w = '';
    if ((($new_id_add != '') || ($new_code_add != ''))) {
        if (($new_code_add == '')) {
            $new_code_add = '11111111111111111111111111111';
        }
        $sql = 'SELECT id_wares, code_wares, partnumber, name_wares, price
  FROM wares WHERE (id_wares = \'' . $new_id_add . '\' or code_wares = \'' . $new_code_add . '\')
  AND visibility <> \'0\' AND amount <> \'0\' AND price <> \'0\'
  ';
        $sth = mysql_query($sql, $connect_mysql);
        $href = mysql_fetch_row($sth);
        $id_wares_add = $href[0];
        $code_wares_add = $href[1];
        $partnumber_add = $href[2];
        $name_wares_add = $href[3];
        $price_add = $href[4];
        $sum_all = $price_add;
        if ((($id_wares_add != '') || ($code_wares_add != ''))) {
            $sql3 = '
 INSERT INTO ware_orders
 (id_orders, id_wares, code_wares, name_wares, amount, price_for_one, partnumber)
 VALUES
 (\'' . $id_orders . '\', \'' . $id_wares_add . '\', \'' . $code_wares_add . '\', \'' . $name_wares_add . '\', \'1\', \'' . $price_add . '\', \'' . $partnumber_add . '\')
 ';
            $sth3 = mysql_query($sql3);
        } else {
            $error_new_w = '
 <br><br>
 <center>
 <b>
 <font color=' . $select . '>
 Продукция не добавлена, так как не может быть продана<br></font></b>
 Возможные причины: цена = 0, количество = 0, видимость = 0,<br> нет такого ID или кода
 </center><br>';
        }
    }
    if (($del_wares_fo != '')) {
        $sql4 = 'DELETE FROM ware_orders WHERE id = ' . $del_wares_fo;
        $sth4 = mysql_query($sql4);
        $sql5 = 'SELECT  amount, price_for_one FROM  ware_orders WHERE id_orders = \'' . $id_orders . '\'';
        $sth5 = mysql_query($sql5);
        while ($hash_ref5 = mysql_fetch_row($sth5)) {
            $amount_new = $hash_ref5[0];
            $price_for_one_new = $hash_ref5[1];
            $sum_all = ($sum_all + (round($amount_new) * $price_for_one_new));
        }
        $update_sum_all = 'yes';
    }
    if (($st_save != '')) {
        $stm = 'UPDATE orders SET status_id = \'' . $st_id . '\', status_date = now() WHERE id_orders = ' . $id_orders;
        $sth = mysql_query($stm);
    }
    if (($usd_course != '')) {
        $stm = 'UPDATE orders SET usd_course = ' . $usd_course . ' WHERE id_orders = ' . $id_orders;
        $sth = mysql_query($stm);
    }
    if (($usd_course_bn != '')) {
        $stm = 'UPDATE orders SET usd_course_bn = ' . $usd_course_bn . ' WHERE id_orders = ' . $id_orders;
        $sth = mysql_query($stm);
    }
    if (($pf_id != '')) {
        $stm = 'UPDATE orders SET payment_face_id = ' . $pf_id . ' WHERE id_orders = ' . $id_orders;
        $sth = mysql_query($stm);
    }
    if (($p_id != '')) {
        $stm = 'UPDATE orders SET payment_id = ' . $p_id . ' WHERE id_orders = ' . $id_orders;
        $sth = mysql_query($stm);
    }
    if (($deliv_id != '')) {
        $stm = 'UPDATE orders SET delivery_id = ' . $deliv_id . ' WHERE id_orders = ' . $id_orders;
        $sth = mysql_query($stm);
    }
    $n = 0;
    while (($amount[$n] != '') && ($order_price[$n] != '')) {
        $stm = 'UPDATE ware_orders SET amount = ' . $amount[$n] . ', price_for_one = ' . $order_price[$n] . '  WHERE id_orders = ' . $id_orders . ' and id_wares = ' . $id_wares[$n];
        $sth = mysql_query($stm);
        if (($sth != '')) {
            $update_sum_all = 'yes';
        }
        $sum_all = ($sum_all + (round($amount[$n]) * $order_price[$n]));
        ++$n;
    }
    if (($update_sum_all != '')) {
        $stm = 'UPDATE orders SET sum_all = \'' . $sum_all . '\' WHERE id_orders = \'' . $id_orders . '\'';
        $sth = mysql_query($stm);
    }
    if (($del_order != '')) {
        $stm = 'DELETE FROM orders WHERE id_orders = \'' . $del_order . '\'';
        $sth = mysql_query($stm);
        $stm = 'DELETE FROM ware_orders WHERE id_orders = \'' . $del_order . '\'';
        $sth = mysql_query($stm);
        $stm = 'DELETE FROM partner_percent WHERE id_orders = \'' . $del_order . '\'';
        $sth = mysql_query($stm);
        print $stm;
    }
    echo '     <table width="100%" border="0" cellspacing="2" cellpadding="3">
  	 <tr>
	 ';
    $stm2 = 'SELECT  status_id, status_name FROM orders_status ORDER BY status_id';
    $sth2 = mysql_query($stm2);
    while ($hash_ref2 = mysql_fetch_row($sth2)) {
        $status_id_menu = $hash_ref2[0];
        $status_name_menu = $hash_ref2[1];
        print '<td align=center bgcolor=#ffffff><a href=index.php?file=orders_admin&st_id=' . $status_id_menu . '><b>' . $status_name_menu . '</b></a></td>';
    }
    echo '     <td align=center bgcolor=#ffffff><a href="index.php?file=orders_admin&st_id=0"><b>Вce</b></a></td>
     </tr>
     </table>
';
    if (($unorder != '')) {
        include 'include/order/ware_unorders.php';
    } else {
        include 'include/order/ware_orders.php';
    }
    return 1;
}

