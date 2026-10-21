<?php
/* EXPERIMENTAL Zend recovery v23. Verify before use. */
$sql = 'SELECT id_wares, name_wares, descript_wares,  belong_groups, new, sellout, amount, description, price, price_old, visibility
FROM wares WHERE ' . $string_where . ' ORDER BY ' . $string_order . ' LIMIT ' . $page_wares . ', ' . $lines_wares;
$sth = mysql_query($sql, $connect_mysql);
$n = 0;
while ($hash_ref = mysql_fetch_row($sth)) {
    $id_wares = $hash_ref[0];
    $name_wares = $hash_ref[1];
    $descript_wares = $hash_ref[2];
    $belong_groups = $hash_ref[3];
    $new = $hash_ref[4];
    $sellout = $hash_ref[5];
    $amount = $hash_ref[6];
    $description = $hash_ref[7];
    $price = $hash_ref[8];
    $price_old = $hash_ref[9];
    $visibility = $hash_ref[10];
    if (($belong_groups != $id_groups)) {
        $link = '&is_l=' . $id_groups;
    } else {
        $link = '';
    }
    $sql1 = 'SELECT count(*) FROM parameters_value WHERE 1 AND id_wares = \'' . $id_wares . '\'';
    $sth1 = mysql_query($sql1);
    $hash_ref1 = mysql_fetch_row($sth1);
    $count_param = $hash_ref1[0];
    $desc_visibility = '';
    if (($count_param != 0)) {
        $desc_visibility = '1';
    }
    if (($description != 0)) {
        $desc_visibility = '1';
    }
    echo '<!--- Блок с товаром -->
<table width="100%" border="0" cellspacing="3" cellpadding="0">
 <tr>
 <td background="';
    print url_prefix();
    echo 'images/pynktir.gif"><img src="';
    print url_prefix();
    echo 'images/pixel.gif" width="1" height="1" alt="" border="0"></td>
 </tr>
 <tr>
 <td><img src="';
    print url_prefix();
    echo 'images/pixel.gif" width="1" height="3" alt="" border="0"></td>
 </tr>
</table>
';
    if ((($search != '') || ($link_n != ''))) {
        echo '<!--- вывод пути для поиска --->
<table width="100%" border="0" cellspacing="2" cellpadding="5" align="center">
 <tr bgcolor="';
        print $color_4;
        echo '">
  <td>';
        path_groups($belong_groups);
        echo '</td>
 </tr>
 <tr>
  <td></td>
 </tr>
</table>
<!--- вывод пути для поиска --->
';
    }
    echo '<table width="100%" height="65" border="0" cellspacing="0" cellpadding="0" align="center">
<tr>
 <td valign="top" rowspan="2">
    <table width="68" height="65" border="0" cellspacing="2" cellpadding="0">
    <tr>
    <td>
	';
    if (($desc_visibility != '')) {
        echo '<a href=';
        out_link('index.php?description=' . $id_wares . $link);
        echo '>
';
    }
    $file_wares_ico = img_parameter('descriptions/img_small', $id_wares, 'file_name');
    if ($file_wares_ico) {
        echo ' <img src="';
        print $file_wares_ico;
        echo '" ';
        print img_parameter('descriptions/img_small', $id_wares, 'html');
        echo ' alt="';
        print out_alt();
        echo '" border="0">
 ';
    } else {
        echo ' <img src="';
        print url_prefix();
        echo 'images/not_img.gif" ';
        print img_parameter('images', 'not_img', 'html');
        echo ' alt="" border="0">
 ';
    }
    if (($desc_visibility != '')) {
        print '</a>';
    }
    echo '
	</td>
    </tr>
    </table>
 </td>
 <td width="100%" valign="top">
<img src="';
    print url_prefix();
    echo 'images/pynkt.gif" alt="';
    print out_alt();
    echo '"  hspace="2" vspace="1" border="0">
';
    if (($desc_visibility != '')) {
        echo '<a href=';
        out_link('index.php?description=' . $id_wares . '&page=' . $n_page . '&id_vendor=' . $id_vendor . $link);
        echo '>';
        print $name_wares;
        echo '</a>&nbsp;
<a href=';
        out_link((url_prefix() . 'cover.php?name=description&description=' . $id_wares . '&page=' . $page . '&id_vendor=' . $id_vendor . '&cover_on=1' . $link));
        echo ' target="_blank"><nobr>[в окне]</nobr></a>
';
    } else {
        print $name_wares;
    }
    echo '<br>
	';
    $descript_wares = out_replace_teg($descript_wares);
    print ($descript_wares . '&nbsp;');
    echo ' </td>
</tr>
<tr>
 <td>

<!-- блок заказа-->
<table width="100%" border="0" cellspacing="3" cellpadding="2" align="right">
<tr>
';
    if ((($id_groups != '') || ($link_n != '') || ($search != ''))) {
        echo '<td width="10" valign="bottom">
';
        if ((10 <= $amount)) {
            $amount_img = '5';
        } else {
            if ((7 <= $amount)) {
                $amount_img = '4';
            } else {
                if ((5 <= $amount)) {
                    $amount_img = '3';
                } else {
                    if ((3 <= $amount)) {
                        $amount_img = '2';
                    } else {
                        if ((1 <= $amount)) {
                            $amount_img = '1';
                        } else {
                            if (($amount == 0)) {
                                $amount_img = '';
                            }
                        }
                    }
                }
            }
        }
        if ((($visibility == '0') || ($price == '0'))) {
            $amount_img = '';
        }
        echo '<img src="';
        print url_prefix();
        echo 'images/amaunt';
        print $amount_img;
        echo '.gif" width="38" height="20" alt="';
        print $name_wares;
        echo ' - количество" border="0"></td>
</td>
';
        $id_compare = array();
        $checked = '';
        $id_compare = explode('|', $compare);
        $i = 0;
        $a = 0;
        while ($id_compare[$i] != '') {
            if (($id_compare[$i] == $id_wares)) {
                $checked = 'checked';
            }
            ++$i;
        }
        echo '<td title="Сравнить продукцию: ';
        print $name_wares;
        echo '" valign="bottom" bgcolor="';
        print $color_2;
        echo '">
 <form action="" name="setCom';
        print $id_wares;
        echo '">
 <table width="100%" border="0" cellspacing="0" cellpadding="0" align="left">
 <tr>
 <td valign="top">
 ';
        echo '<s';
        echo 'cript>function sw';
        print $id_wares;
        echo '(id){setCompare(document.setCom';
        print $id_wares;
        echo '.compare';
        print $id_wares;
        echo '.checked,id)}</script>
 <input style="background: ';
        print $color_2;
        echo '; border: ';
        print $color_2;
        echo ';"  ';
        print $checked;
        echo ' type="checkbox" ';
        print $stile_for_checkbox;
        echo ' name="compare';
        print $id_wares;
        echo '"  onClick="sw';
        print $id_wares;
        echo '(';
        print $id_wares;
        echo ')">
 </td>
 <td><a href="#" onClick="window.open(\'';
        print url_prefix();
        echo 'cover.php?name=compare&id_groups=';
        print $id_groups;
        echo '\',\'Compare\', \'resizable=yes, top=20, left=20 , width=600, height=400,location=no,status=no,scrollbars=yes\');return false;"><img src="';
        print url_prefix();
        echo 'images/scales.gif" width="31" height="16" alt="Сравнить продукцию: ';
        print $name_wares;
        echo '" border="0"></a></td>
 </tr>
 </table>
</form>
</td>

';
        if (($new != 0)) {
            echo '<td width=10 valign="bottom">
<img src="';
            print url_prefix();
            echo 'images/new.gif"  width="36" height="17" alt="';
            print $name_wares;
            echo ' - новинка" border=0>
</td>
';
        }
        if (($sellout != 0)) {
            echo '<td width=20 align=right valign="bottom">
<img src="';
            print url_prefix();
            echo 'images/sellout.gif"  alt="';
            print $name_wares;
            echo ' - цена снижена" border=0>
</td>
';
        }
        echo '	
<td width="100%" valign="bottom">&nbsp;</td>
';
    }
    echo '
<td align="right">
<b>
';
    if ((($visibility == '0') || ($amount == '0') || ($price == '0'))) {
        echo '<a href="#" onClick="window.open(\'';
        print url_prefix();
        echo 'cover.php?link_n=10&id_wares=';
        print $id_wares;
        echo '\',\'Wares_for_order\', \'resizable=yes, top=20, left=20 , width=600, height=400,location=no,status=no,scrollbars=yes\');return false;">заказать</a>
';
        $yes_buy = 'y';
    } else {
        echo '<font title="Действующая цена">';
        print out_price($price, $currency, $CurTypeID, 'user', 'cur_rate_nal');
        echo '</font><br>
 ';
        if (($price_old != 0)) {
            echo ' <font title="Старая цена -';
            print strip_tags(out_price($price_old, $currency, $CurTypeID, 'user', 'cur_rate_nal'));
            echo '" color="';
            print $select;
            echo '">';
            echo '<s';
            echo '>';
            print out_price($price_old, $currency, $CurTypeID, 'user', 'cur_rate_nal');
            echo '</s></font>
 ';
        }
        $yes_buy = 'n';
    }
    echo '</b>
</td>
';
    if (($yes_buy != 'y')) {
        echo '<form action="';
        print url_prefix();
        echo 'index.php?';
        print $QUERY_STRING;
        echo '" method="post"> 
<td width="10" valign="bottom">
<input type="text" name="amount_buy[]" value="1" size="2">
<input type="hidden" name="id_groups" value="';
        print $id_groups;
        echo '">
<input type="hidden" name="id_wares_buy[]" value="';
        print $id_wares;
        echo '">
<input type="hidden" name="sg_wares" value="';
        print $sg_wares;
        echo '">
<input type="hidden" name="sg_desk" value="';
        print $sg_desk;
        echo '">
</td>

<td width="10">
шт.
</td>

<td width="10" valign="bottom">
<input type="image" src="';
        print url_prefix();
        echo 'images/buy.gif" alt="';
        print $name_wares;
        echo ' - купить" border="0" style="border: none; background: transparent;">
</td>
';
    }
    echo '</tr>
</table>
</form>
<!-- /блок заказа-->

 </td>
</tr>
</table>
';
    ++$n;
}
if (($n == 0)) {
    include 'include/wares/wares_advert.php';
}
echo '<!--- /Блок с товаром --->
';
return 1;

