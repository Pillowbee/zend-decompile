<?php
/* EXPERIMENTAL Zend recovery v21. Verify before use. */
echo '<table width="100%" border="0" cellspacing="2" cellpadding="5" align="center">
<tr>
<td colspan="8" bgcolor="';
print $white;
echo '">
';
path_groups($id_groups);
$sql = 'SELECT  id_profile, name_profile, sm_name_profile FROM export_profiles WHERE visibility = \'1\'';
$sth = mysql_query($sql, $connect_mysql);
$n = 0;
while ($hash_ref = mysql_fetch_row($sth)) {
    $id_profile[$n] = $hash_ref[0];
    $name_profile[$n] = $hash_ref[1];
    $sm_name_profile[$n] = $hash_ref[2];
    ++$n;
}
echo ' </td>
 <td rowspan="2" bgcolor="';
print $white;
echo '"><img src="images/ico_group.gif" width="21" height="60" alt="">
<a href="index.php?file=wares_admin&switch=2&id_groups=';
print $id_groups;
echo '">
';
$file_name = img_parameter('images/group_ico', $id_groups, 'file_name');
if (($file_name != '')) {
    echo '<img src="';
    print $file_name;
    echo '" ';
    img_parameter('images/group_ico', $id_groups, 'html');
    echo ' alt="Иконка для группы продукции и для отдельных товаров без иконки в этой группе" border=0>
';
} else {
    echo '<img src="../images/not_img.gif" alt="Иконка для группы продукции и для отдельных товаров без иконки в этой группе" width="60" height="60" border="0">
';
}
echo '</a>
 </td>
 <td colspan="';
print count($id_profile);
echo '" title="Разрешить отображать группу в профиле">экспорт</td>
</tr>
<tr>
 <td align="center" bgcolor="';
print $color_light_1;
echo '" title="Номер по порядку">№<br>п.п.</td>
 <td align="center" bgcolor="';
print $color_light_1;
echo '" title="Удалить позицию"><img src="../images/delete.gif" width="13" height="13" alt="Удалить позицию" border="0"></td>
 <td align="center" bgcolor="';
print $color_light_1;
echo '" title="Не разрешать индексировать позицию поисковыми системами"><a href="#" onClick="SelectAll(\'groups_noindex\')"><img src="../images/not_search.gif" width="16" height="16" alt="Не разрешать индексировать позицию поисковыми системами" border="0"></a></td>
 <td align="center" bgcolor="';
print $color_light_1;
echo '" title="Переместить позицию"><img src="../images/move.gif" width="16" height="13" alt="Переместить позицию" border="0"></td>
 <td align="center" bgcolor="';
print $color_light_1;
echo '" title="Видимость позиции на сайте"><img src="../images/visibility.gif" width="16" height="16" alt="Видимость позиции на сайте" border="0"></td>
 <td align="center" bgcolor="';
print $color_light_1;
echo '"></td>
 <td colspan=2 align="center" bgcolor="';
print $color_light_1;
echo '">Название группы</td>

';
$a = 0;
while ($a < count($id_profile)) {
    echo '   <td title="';
    print $name_profile[$a];
    echo '" bgcolor="';
    print $white;
    echo '">';
    print $sm_name_profile[$a];
    echo '</td>
';
    ++$a;
}
echo '</tr>
';
$statement = 'SELECT id_groups, sort_groups, belong_groups, name_groups, visibility, meta_noindex FROM groups WHERE belong_groups = \'' . $id_groups . '\' ORDER BY sort_groups';
$sth = mysql_query($statement, $connect_mysql);
$n = 0;
$i = 1;
$id_belong_groups = '';
while ($aref = mysql_fetch_row($sth)) {
    $id_belong_groups = $aref[0];
    $sort_groups = $aref[1];
    $number_groups = $aref[2];
    $name_groups = $aref[3];
    $visibility_groups = $aref[4];
    $meta_noindex = $aref[5];
    if (($meta_noindex == 0)) {
        $checked = '';
    } else {
        $checked = 'checked';
    }
    if (($visibility_groups == 0)) {
        $vis_attr = 1;
        $visibility_groups_text = (('<font color=' . $select) . '>нет</font>');
    } else {
        if (($visibility_groups == 1)) {
            $vis_attr = 0;
            $visibility_groups_text = ' + ';
        }
    }
    echo ' <tr>
   <td width=1% bgcolor=';
    print $white;
    echo '><input type="text" name="number_pp[]" value="';
    print $sort_groups;
    echo '" size="2"></td>
   <td width=1% align="center" bgcolor=';
    print $white;
    echo '><a style="text-decoration: none;" title="удалить" href="index.php?file=wares_admin&del_groups=';
    print $id_belong_groups;
    echo '&id_groups=';
    print $id_groups;
    echo '"><b>X</b></a></td>
   <td align="center" title="Не разрешать индексировать позицию поисковыми системами" bgcolor=';
    print $white;
    echo '><input ';
    print $checked;
    echo ' type="checkbox" id="groups_noindex" name="groups_noindex[';
    print ($i - 1);
    echo ']" value="1" style="border: none;"></td>
   <td width=1% align="center" bgcolor=';
    print $white;
    echo '><a style="text-decoration: none;" title="переместить" href="index.php?file=groups_move&move_groups=';
    print $id_belong_groups;
    echo '&sg_wares=';
    print $sg_wares;
    echo '&sg_desk=';
    print $sg_desk;
    echo '"><img src="../images/move.gif" width="16" height="13" alt="Переместить позицию" border="0"></a></td>
   <td width=1% align="center" bgcolor=';
    print $white;
    echo '>
    ';
    if (($id_groups != '')) {
        $sql1 = 'SELECT visibility FROM groups WHERE id_groups = \'' . $id_groups . '\'';
        $sth1 = mysql_query($sql1);
        $aref1 = mysql_fetch_row($sth1);
        $visibility_gr = $aref1[0];
    } else {
        $visibility_gr = 1;
    }
    if (($visibility_gr != 0)) {
        echo '    <a style="text-decoration: none;" title="Видимость позиции на сайте" href="index.php?file=wares_admin&vis_groups=';
        print $id_belong_groups;
        echo '&id_groups=';
        print $id_groups;
        echo '&vis_attr=';
        print $vis_attr;
        echo '">';
        print $visibility_groups_text;
        echo '</a>	
	';
    } else {
        print '<p title=\'Изменить видимость невозможно\'>---</p>';
    }
    echo '   </td>
   <td><a style="text-decoration: none;" href="index.php?file=wares_admin&id_groups=';
    print $id_belong_groups;
    echo '&sg_wares=';
    print $sg_wares;
    echo '&sg_desk=';
    print $sg_desk;
    echo '">воити&nbsp;в</a></td>
   <td colspan=3 width=40% bgcolor="';
    print $white;
    echo '"><a title="Просмотр в новом окне" href="../index.php?id_groups=';
    print $id_belong_groups;
    echo '" target="_blank"><img src="../images/eye.gif" width="15" height="11" border="0" align="left" vspace="5"></a><input title="';
    print $name_groups;
    echo '" style="width: 98%;" type=text name="name_groups_change[]" value="';
    print $name_groups;
    echo '" size=20><input type="hidden" name="id_groups_change[]" value="';
    print $id_belong_groups;
    echo '"></td>
';
    $a = 0;
    while ($a < count($id_profile)) {
        echo '   <td title="Выводить позицию в профиле --';
        print $name_profile[$a];
        echo '--" bgcolor="';
        print $white;
        echo '"><input type="checkbox" name="';
        print (((('profile' . $id_profile[$a]) . '[') . $i) . ']');
        echo '" value="1" style="border: none;"></td>
';
        ++$a;
    }
    echo '</tr>
   ';
    ++$n;
    ++$i;
}
if (($id_belong_groups == '')) {
    print '<tr><td colspan=10 align=center bgcolor=' . $white . '><b>Группы отсутствуют</b></td></tr>';
}
echo '   
<tr>
  <td colspan="6" align="center" bgcolor=';
print $white;
echo '><center>добавить группу</center></td>
  <td width="100%" bgcolor=';
print $white;
echo '><input style="width: 99%;" type=text name="name_groups_new" value="" size=20></td>
  <td colspan="2" ><input type=submit value=сохранить></td>
</tr>

<tr>
<td colspan="9" align="center"><font color=';
print $select;
echo '>';
print $error_del;
echo '</font>&nbsp;</td>
</tr>

</table>
';
if (($table_wares != '')) {
    echo '<s';
    echo 'cript>
location.href="index.php?file=wares_admin&id_groups=';
    print $id_groups;
    echo '&page=';
    print $page;
    echo '&sg_wares=';
    print $sg_wares;
    echo '&sg_desk=';
    print $sg_desk;
    echo '#table_wares";
</script>
';
}
echo '
<table width="100%" border="0" cellspacing="2" cellpadding="5" align="center">
<tr>
 <td bgcolor=';
print $white;
echo '>

<a name="table_wares"></a>
<table width="100%" border="0" cellspacing="3" cellpadding="5">
<tr>
<td  width="100%" bgcolor=';
print $color_4;
echo '>

<table>
<tr>
	<td>Поиск</td>
	<td><input type="text" name="search" value="';
print $search;
echo '"></td>
	<td><input type="submit" value=">>>"></td>
</tr>
</table>

</td>
<td>
';
$id_sort = 2;
include 'include/sort_default.php';
echo '</td>
</tr>
';
$string_order = sort_default(2);
$string_where .= '(belong_groups = \'' . $id_groups . '\' ';
$sql2 = 'SELECT id_wares FROM `wares_links` WHERE belong_groups = \'' . $id_groups . '\'';
$sth2 = mysql_query($sql2);
while ($hash_ref2 = mysql_fetch_row($sth2)) {
    $id_wares_link = $hash_ref2[0];
    $string_where .= 'OR id_wares = \'' . $id_wares_link . '\' ';
}
$string_where .= ')';
if (($search != '')) {
    $string_where .= ' HAVING st_search1 LIKE Lcase(\'%' . $search . '%\')';
}
$stm = 'SELECT id_wares, sort_wares, name_wares, descript_wares,  belong_groups, new, sellout, amount, description, price, shop_win, code_wares,visibility,meta_noindex,
 Lcase(CONCAT(id_wares,\' \',sort_wares,\' \',name_wares,\' \',descript_wares,\' \',code_wares)) AS st_search1, price_old
FROM wares
WHERE ' . $string_where . ' ORDER BY ' . $string_order;
echo '<tr>
 <td colspan="2">
 ';
page_links_out($stm, $lines_wares_admin);
echo ' </td>
</tr>
</table>
<a name="1" id="1">&nbsp;</a>
</td></tr><table>
<table width="100%" border="0" cellspacing="2" cellpadding="2" align="center">
<tr bgcolor="';
print $color_light_1;
echo '">
    <td align="center" title="Позиция">&nbsp;</td>
	<td align="center" title="Уникальный ID">ID(код)</td>
	<td align="center" title="Номер по порядку">№<br>п.п.</td>
	<td align="center" title="Удалить позицию"><img src="../images/delete.gif" width="13" height="13" alt="Удалить позицию" border="0"></td>
    <td align="center" bgcolor="';
print $color_light_1;
echo '" title="Неразрешать индексировать позицию поисковыми системами"><a href="#1" onClick="SelectAll(\'wares_noindex\')"><img src="../images/not_search.gif" width="16" height="16" alt="Не разрешать индексировать позицию поисковыми системами" border="0"></a></td>
	<td align="center" title="Пререместить позицию или создать ссылку"><img src="../images/move.gif" width="16" height="13" alt="Переместить позицию" b';
echo 'order="0"></td>
	<td align="center" title="Редактировать позицию"><img src="../images/edit.gif" width="13" height="13" alt="Редактировать позицию" border="0"></td>
	<td align="center" title="Отображать на витрине"><img src="../images/win1.gif" width="14" height="16" alt="Отображать на витрине" border="0"></td>
	<td align="center" title="Описание"><img src="../images/descript.gif" width="13" height="16" ';
echo 'alt="Описание" border="0"></td>
	<td align="center" title="Технические характеристики"><b>тх</b></td>
	<td title="Видимость на сайте"><a href="#1" onClick="SelectAll(\'visibility\')"><img src="../images/visibility.gif" width="16" height="16"  alt="Видимость на сайте" border="0"></a></td>
	<td align="center">Название продукции</td>
	<td align="center">кол&nbsp;во</td>
	<td align="center">цена</td>
	<td align="c';
echo 'enter"><a href="#1" onClick="SelectAll(\'price_old\')"><img src="../images/price_old.gif" width="17" height="20" alt="Запомнить старую цену" border="0"></td>
</tr>	
';
$statement = ($stm . ' LIMIT ' . $page_wares_admin . ', ' . $lines_wares_admin);
$sth = mysql_query($statement);
$m = 0;
$pos = ($page_wares_admin + 1);
while ($hash_ref = mysql_fetch_row($sth)) {
    $id_wares = $hash_ref[0];
    $sort_wares = $hash_ref[1];
    $name_wares = $hash_ref[2];
    $descript_wares = $hash_ref[3];
    $belong_groups = $hash_ref[4];
    $new = $hash_ref[5];
    $sellout = $hash_ref[6];
    $amount = $hash_ref[7];
    $description = $hash_ref[8];
    $price = $hash_ref[9];
    $shop_win = $hash_ref[10];
    $code_wares = $hash_ref[11];
    $visibility = $hash_ref[12];
    $meta_noindex = $hash_ref[13];
    $price_old = $hash_ref[15];
    echo '<tr>
    <td width="1%" bgcolor=';
    print $white;
    echo ' aling="center">';
    print $pos;
    echo '</td>
  	<td width="1%" bgcolor=';
    print $white;
    echo ' aling="center">';
    print $id_wares;
    echo '(';
    print $code_wares;
    echo ')</td>
  	<td width="1%" bgcolor=';
    print $white;
    echo '>
	<input type="text" name="sort_wares[]" value="';
    print $sort_wares;
    echo '" size="2">
	</td>
	<td width="1%" align="center" bgcolor=';
    print $white;
    echo '>
';
    if (($belong_groups != $id_groups)) {
        echo '<a title="Удалить ссылку" href="index.php?file=wares_admin&del_link=';
        print $id_wares;
        echo '&id_groups=';
        print $id_groups;
        echo '&page=';
        print $page;
        echo '#table_wares"><b>X</b></a></td>
';
    } else {
        echo '<a title="Удалить позицию" href="index.php?file=wares_admin&del_wares=';
        print $id_wares;
        echo '&id_groups=';
        print $id_groups;
        echo '&page=';
        print $page;
        echo '#table_wares"><b>X</b></a></td>
';
    }
    echo '    <td title="Не разрешать индексировать позицию поисковыми системами"><input ';
    if (($meta_noindex == 1)) {
        print 'checked';
    }
    echo ' type="checkbox" id="wares_noindex" name="wares_noindex[';
    print $m;
    echo ']" value="1" style="border: none;"></td>	
    <td width="1%" align="center" bgcolor=';
    print $white;
    echo '>
	
';
    $id_move_ware = array();
    $checked = '';
    $id_move_ware = explode('|', $move_ware);
    $i = 0;
    $a = 0;
    while ($id_move_ware[$i] != '') {
        if (($id_move_ware[$i] == $id_wares)) {
            $checked = 'checked';
        }
        ++$i;
    }
    echo '   

 ';
    if (($belong_groups != $id_groups)) {
        if (($belong_groups == 0)) {
            $name_groups_temp = 'ПРОДУКЦИЯ';
        } else {
            $sql3 = 'SELECT name_groups FROM groups WHERE id_groups = \'' . $belong_groups . '\'';
            $sth3 = mysql_query($sql3);
            $hash_ref3 = mysql_fetch_row($sth3);
            $name_groups_temp = $hash_ref3[0];
        }
        echo '  <td width="1%" align="center" bgcolor=';
        print $white;
        echo '>
  <a title="Ссылка на опитание в раздел - ';
        print $name_groups_temp;
        echo '" href="index.php?file=wares_change&id_groups=';
        print $belong_groups;
        echo '&wares_change=';
        print $id_wares;
        echo '&page=';
        print $n_page;
        echo '&sg_wares=';
        print $sg_wares;
        echo '&sg_desk=';
        print $sg_desk;
        echo '#table_wares"><b>ссылка</b></a>
  </td>
 ';
    } else {
        echo ' <table width="100%" border="0" cellspacing="0" cellpadding="2" align="left" bgcolor="';
        print $color_2;
        echo '">
 <tr>
 <td title="Пререместить позицию или создать ссылку">
 ';
        echo '<s';
        echo 'cript>function smw';
        print $id_wares;
        echo '(id){setMove_ware(document.form_admin.move_ware';
        print $id_wares;
        echo '.checked,id)}</script>
 <input style="background: ';
        echo '; border: none;" ';
        print $checked;
        echo ' type="checkbox" ';
        print $stile_for_checkbox;
        echo ' name="move_ware';
        print $id_wares;
        echo '"  onClick="smw';
        print $id_wares;
        echo '(';
        print $id_wares;
        echo ')">
 </td>
 <td><a href="index.php?file=wares_move&id_groups=';
        print $id_groups;
        echo '"><img src="../images/move.gif" width="16" height="13" alt="Пререместить позицию или создать ссылку" border="0"></a></td>
 </tr>
 </table>

<td width="1%" align="center" bgcolor=';
        print $white;
        echo '><a href="index.php?file=wares_change&id_groups=';
        print $id_groups;
        echo '&wares_change=';
        print $id_wares;
        echo '&page=';
        print $n_page;
        echo '&sg_wares=';
        print $sg_wares;
        echo '&sg_desk=';
        print $sg_desk;
        echo '#table_wares">ред.</a></td>
';
    }
    echo '
	';
    if (($shop_win == 1)) {
        $checked = 'checked';
    } else {
        $checked = '';
    }
    echo '	<td align="center">
	<input type="checkbox" name="shop_win[';
    print $m;
    echo ']" value="';
    print $id_wares;
    echo '" style="border: none;" ';
    print $checked;
    echo '></td>
	
	<td align="center">
	';
    if (($description == '0')) {
        print '<font color=' . $select . '><b>-</b></font>';
    } else {
        print '+';
    }
    echo '	</td>
    <td  align="center">
	';
    $sql1 = 'SELECT count(*) FROM `parameters_value` WHERE id_wares = ' . $id_wares;
    $sth1 = mysql_query($sql1);
    $hash_ref1 = mysql_fetch_row($sth1);
    $count_id_wares = $hash_ref1[0];
    if (($count_id_wares == 0)) {
        print '<font color=' . $select . '><b>-</b></font>';
    } else {
        print '<b>+</b>';
    }
    echo '	</td>
	<td align="center">
	';
    if (($visibility == 1)) {
        $checked = 'checked';
    } else {
        $checked = '';
    }
    echo '	<input type="checkbox" id="visibility" name="visibility[';
    print $m;
    echo ']" ';
    print $checked;
    echo ' value="1" style="border: none;">
	</td>
	
	<td width="100%" bgcolor=';
    print $white;
    echo '>

<div id="eye';
    print $id_wares;
    echo '" style="z-index: 1; position: absolute; visibility: hidden;">
';
    $file_name = img_parameter('descriptions/img_small', $id_wares, 'file_name');
    if (($file_name != '')) {
        echo '<table bgcolor="#000000" border="0" cellspacing="0" cellpadding="5">
<tr>
	<td bgcolor="#FFFFFF"><img src="';
        print $file_name;
        echo '" border="1"></td>
</tr>
</table>
';
    } else {
        echo '<table bgcolor="#000000" border="0" cellspacing="1" cellpadding="5">
<tr>
	<td bgcolor="#FFFFFF">иконки&nbsp;нет</td>
</tr>
</table>
';
    }
    echo '</div>
<div id="view_export';
    print $id_wares;
    echo '" style="z-index: 1; position: absolute; visibility: hidden;">
<table border="0" cellspacing="0" cellpadding="1">
 <tr><td bgcolor="';
    print $color_1;
    echo '"><a style="cursor: pointer;" onclick="layer_close(\'export';
    print $id_wares;
    echo '\')"><img src="../images/close_sm.gif" width="9" height="9" alt="Закрыть форму без сохранения"></a></td></tr>
<tr>
<td bgcolor="';
    print $color_1;
    echo '">

<table border="0" cellspacing="0" cellpadding="0" bgcolor="#ffffff">
 <tr>
 <td style="padding-left: 3px;">ЯМ</td>
 <td><input type="checkbox" value="1" style="border-style: none;"></td>
 <td bgcolor="';
    print $color_1;
    echo '"><img src="../images/pixel.gif" width="1" height="1" alt=""></td>
 <td style="padding-left: 3px;">РП</td>
 <td><input type="checkbox" value="1" style="border-style: none;"></td>
 <td bgcolor="';
    print $color_1;
    echo '"><img src="../images/pixel.gif" width="1" height="1" alt=""></td>
  <td style="padding-left: 3px;">CSV</td>
 <td><input type="checkbox" value="1" style="border-style: none;"></td>
 </tr>
</table>

</td></tr></table>
</div>

<div id="export';
    print $id_wares;
    echo '" style="z-index: 1; position: absolute; visibility: hidden;">
<table border="0" cellspacing="0" cellpadding="1">
 <tr><td bgcolor="';
    print $color_1;
    echo '"><a style="cursor: pointer;" onclick="layer_close(\'export';
    print $id_wares;
    echo '\')"><img src="../images/close_sm.gif" width="9" height="9" alt="Закрыть форму без сохранения"></a></td></tr>
<tr>
<td bgcolor="';
    print $color_1;
    echo '">

<table border="0" cellspacing="0" cellpadding="0" bgcolor="#ffffff">
 <tr>
 <td style="padding-left: 3px;">ЯМ</td>
 <td><input type="checkbox" value="1" style="border-style: none;"></td>
 <td bgcolor="';
    print $color_1;
    echo '"><img src="../images/pixel.gif" width="1" height="1" alt=""></td>
 <td style="padding-left: 3px;">РП</td>
 <td><input type="checkbox" value="1" style="border-style: none;"></td>
 <td bgcolor="';
    print $color_1;
    echo '"><img src="../images/pixel.gif" width="1" height="1" alt=""></td>
  <td style="padding-left: 3px;">CSV</td>
 <td><input type="checkbox" value="1" style="border-style: none;"></td>
 </tr>
</table>

</td></tr></table>
</div>

<table width="100%" border="0" cellspacing="0" cellpadding="0">
<tr>
   <td>

<table border="0" cellspacing="0" cellpadding="0">
<tr>
	<td><a onmousemove="layer_visibility(\'visible';
    echo '\',\'eye';
    print $id_wares;
    echo '\')" onmouseout="layer_visibility(\'hidden\',\'eye';
    print $id_wares;
    echo '\')" href="../index.php?description=';
    print $id_wares;
    echo '" target="_blank"><img src="../images/eye.gif" alt="" width="15" height="11" border="0" style="margin-right: 3px;"></a></td>
	<td><a name="link_export';
    print $id_wares;
    echo '" id="link_export';
    print $id_wares;
    echo '" style="cursor: pointer;" onClick="test(\'export';
    print $id_wares;
    echo '\')" onMouseMove="layer_visibility(\'visible\',\'view_export';
    print $id_wares;
    echo '\')" onMouseOut="layer_visibility(\'hidden\',\'view_export';
    print $id_wares;
    echo '\')">экспорт</a></td></td>
</tr>
</table>

   </td>
</tr>
<tr>
	<td colspan="2"><input id=see_export';
    print $id_wares;
    echo ' type="text" name="name_wares_change[]" value="';
    print $name_wares;
    echo '" size="50" style="width: 98%;"></td>
</tr>
</table>

	</td>
	<td width="10" bgcolor=';
    print $white;
    echo '><input type=text name="amount_change[]" value=';
    print $amount;
    echo ' size=3></td>
	<td width="10" bgcolor=';
    print $white;
    echo '><input type=text name="price_change[]" value=';
    print $price;
    echo ' size=5>
	<input type="hidden" name="id_wares_change[]" value="';
    print $id_wares;
    echo '">
	</td>
	<td title="Запомнить старую цену"><input type="checkbox" id="price_old" name="price_old[';
    print $m;
    echo ']" value="';
    print $price;
    echo '" ';
    if (($price_old == '0')) {
        print 'style="border: none;"';
    } else {
        print 'style="border-color: ' . $select . ';"';
    }
    echo '></td>
</tr>

';
    ++$m;
    ++$pos;
}
if (($id_wares == '')) {
    echo '<tr>
 <td colspan="11" bgcolor=';
    print $white;
    echo '><center><b>Продукция отсутствует</b></center></td>
</tr>
';
}
echo '<tr>
  	<td align="right" colspan="11" bgcolor=';
print $white;
echo '>добавить продукцию</td>
	<td width="100%" bgcolor=';
print $white;
echo '>
	<input type="text" name="name_wares_new" size="50" style="width: 99%;">
	</td>
	<td width="11" bgcolor=';
print $white;
echo '><input type=text name="amount_new" value="" size=3></td>
	<td width="11" bgcolor=';
print $white;
echo '><input type=text name="price_new" value="" size=5></td>
</tr>
<tr>
    <td colspan="11" bgcolor=';
print $white;
echo '>&nbsp;</td>
	<td colspan="3" bgcolor=';
print $white;
echo '><input type="submit" value="Сохранить"></td>
</tr>
<tr>
    <td colspan="14" bgcolor=';
print $white;
echo '>
	';
page_links_out($stm, $lines_wares_admin);
echo '	</td>
</tr>
</table>
<br>
<table width="100%" border="0" cellspacing="2" cellpadding="2" align="left">
<tr>
<td width="17" valign="top" bgcolor="#FFFFFF"><img src="../images/price_old.gif" width="17" height="20" alt="" border="0"></td>
<td bgcolor="#ffffff">
<li>Проставленная галочка в этом поле позволяет сохранить текущую цену, как старую. А вместо текущей набрать новую и одним нажатием кнопки "сох';
echo 'ранить" сделать изменения для всех позиций.
<li>Для удаления/изменения старой цены, необходимо кликнуть на ссылку "ред.", войти в расширенный редактор описания
и произвести необходимые действия.
<li>Подсвеченное цветом поле с галкой означает что у этой позиции есть старая цена.
</td>
</tr>
</table>
';
return 1;

