<?php
/* EXPERIMENTAL Zend recovery v23. Verify before use. */
check_database($key, $key1, $connect_mysql, $db_name);
if ((right_set_admin($REMOTE_USER, 'import') == 0)) {
    include 'include/rights_txt/viewing_pages.php';
    return NULL;
} else {
    echo '<input type="hidden" name="file" value="import">
<table width="100%" border="0" cellspacing="2" cellpadding="5" align="center">
<tr>
    <td colspan="4" align="center" bgcolor="';
    print $color_2;
    echo '">
	<b>ИМПОРТ ДАННЫХ</b></td>
</tr>
<tr>
<td bgcolor="';
    print $white;
    echo '">
<img src="../images/pynkt.gif" width="4" height="7" hspace="4" alt="" border="0">&nbsp;<font color=';
    print $select;
    echo '><b>ЭТАП 1</b></font><br>
Загрузить&nbsp;CSV&nbsp;файл&nbsp;c&nbsp;данными<br>
</td>
<td bgcolor="';
    print $white;
    echo '">
<input type="file" name="file_csv">&nbsp;&nbsp;<input type="submit" value="Загрузить">
</td>
<tr>
 <td colspan="2" bgcolor="';
    print $white;
    echo '">
';
    if ((($file_csv != 'none') && ($file_csv != ''))) {
        move_uploaded_file($file_csv, 'upload/datafile.csv');
    }
    if (file_exists('upload/datafile.csv')) {
        $file_size = filesize('upload/datafile.csv');
        echo '<center>Файл размером <b>';
        print $file_size;
        echo ' байт</b> с данными загружен.</center>
';
    } else {
        echo ' 
 Для импорта используется файл с разделителями ";" формата CSV (MS Excel)<br>
 Пример файла можно скачать: <a href="upload/test_xls.zip">test_xls.zip</a>(186 кбайт)<br>
 Перед импортом в магазин его необходимо сохранить как CSV.
';
    }
    echo ' </td>
</tr>
<tr>
 <td colspan="2">&nbsp;</td>
</tr>

<tr>
  <td bgcolor="';
    print $white;
    echo '">
  <img src="../images/pynkt.gif" width="4" height="7" hspace="4" alt="" border="0">&nbsp;<font color=';
    print $select;
    echo '><b>ЭТАП 2</b></font><br>
  Преобразование текстового файла в SQL
  </td>
  <td bgcolor="';
    print $white;
    echo '">
  ';
    if ($file_size) {
        echo '  <input type="submit" name="new_data" value="Текстовый файл -> SQL"><br><br>
  <a href="cover.php?name=vis_position" target="_blanr">[Пометить&nbsp;отсутствующие&nbsp;позиции&nbsp;как&nbsp;скрытые]</a><br>
  ';
    } else {
        echo '&nbsp;
  ';
    }
    echo '</td>
</tr>
<tr>
 <td colspan="2"  bgcolor="';
    print $white;
    echo '">
';
    if (($new_data != '')) {
        $sql = 'DELETE FROM `import`';
        $sth = mysql_query($sql, $connect_mysql);
        $row = 1;
        $row_all = 1;
        $err = 1;
        $fp = fopen('upload/datafile.csv', 'r');
        while (!feof($fp)) {
            $line = fgets($fp, 4096);
            $data = explode(';', $line);
            if (($data[0] != '')) {
                $group_name = $data[0];
            } else {
                if (($data[1] != '')) {
                    $sub_group_name = $data[1];
                    $vendor = '';
                }
            }
            if (($data[2] != '')) {
                $vendor = $data[2];
            }
            if (is_numeric($data[3])) {
                $price = ereg_replace(',', '.', $data[6]);
                $price = ereg_replace(' ', '', $price);
                $name_wares = ereg_replace('\'', '`', $data[4]);
                $name_wares = ereg_replace('"', '&quot;', $name_wares);
                $group_name = ereg_replace('"', '&quot;', $group_name);
                $group_name = ereg_replace('\\\'', '`', $group_name);
                $sub_group_name = ereg_replace('"', '&quot;', $sub_group_name);
                $sub_group_name = ereg_replace('\\\'', '`', $sub_group_name);
                $partnumber = ereg_replace('"', '&quot;', $data[5]);
                $partnumber = ereg_replace('\\\'', '`', $partnumber);
                $vendor = ereg_replace('"', '&quot;', $vendor);
                $vendor = ereg_replace('\\\'', '`', $vendor);
                $amount = ($data[7] + $data[8]);
                if (($amount != 0)) {
                    $sql = 'INSERT INTO import SET
groups = \'' . $group_name . '\',
subgroups = \'' . $sub_group_name . '\',
vendor = \'' . $vendor . '\',
code_wares = \'' . $data['3'] . '\',
name_wares = \'' . $name_wares . '\',
partnumber = \'' . $partnumber . '\',
price = \'' . $price . '\',
sclad = \'' . $data['7'] . '\',
transit = \'' . $data['8'] . '\',
deliver = \'' . $data['9'] . '\',
data_deliver = \'' . $data['10'] . '\',
warranties = \'' . $data['11'] . '\'
';
                    $sth = mysql_query($sql, $connect_mysql);
                    ++$row;
                }
                if ((mysql_errno() != 0)) {
                    print (((('Строка <b>' . $row_all . '</b> Ошибка <b>' . mysql_errno()) . ': </b>') . mysql_error()) . '<BR>');
                    print (('<b>В запросе-</b>' . $sql) . '<br><br>');
                    ++$err;
                }
            }
            ++$row_all;
        }
        fclose($fp);
        $err = ($err - 1);
        $skip = ($row_all - ($row - 1));
        $row = (($row - 1) - $err);
        print '<center>В файле <b>' . $row_all . '</b> строк(и). Преобразованно <b>' . $row . '</b> строк(и). Пропущено <b>' . $skip . '</b> строк(и). Ошибок <b>' . $err . '</b></center>';
        $count_wares = $row;
    } else {
        $sql = 'SELECT count(id_import) FROM import';
        $sth = mysql_query($sql, $connect_mysql);
        $hash_ref = mysql_fetch_row($sth);
        $count_wares = $hash_ref[0];
        if (($count_wares != 0)) {
            print '<center>Доступно для импорта <b>' . $count_wares . '</b> строк(и)</center>';
        } else {
            echo '  Преобразование требует ресурсов от сервера и
  в зависимости от размера импортируемого файла может длиться от 5 до 30 секунд.
';
        }
    }
    echo '</td></tr>
<tr>
 <td colspan="2">&nbsp;</td>
</tr>

<tr>
 <td valign="top" bgcolor="';
    print $white;
    echo '">
  <img src="../images/pynkt.gif" width="4" height="7" hspace="4" alt="" border="0">&nbsp;<font color=';
    print $select;
    echo '><b>ЭТАП 3</b></font><br>
  Импортирование данных в ИНТЕРНЕТ МАГАЗИН</td>
 <td bgcolor="';
    print $white;
    echo '">
 ';
    if (($count_wares != 0)) {
        echo ' <table width="80%" border="0" cellspacing="3" cellpadding="2">
<tr>
	<td align="right">Коэффициент для цены:</td>
	<td bgcolor="';
        print $color_2;
        echo '"><input type="text" name="factor" value="1" size="4"></td>
</tr>
<tr>
	<td align="right">Удалить временные данные</td>
	<td bgcolor="';
        print $color_2;
        echo '"><input type="checkbox" name="del_temp" value="yes"></td>
</tr>
<tr>
	<td colspan="2"><input type=hidden name=file value=import>
 <input type=submit name=update_wares value="импорт в МАГАЗИН"></td>
</tr>
</table>
 ';
    }
    echo ' </td>
</tr>

<tr>
 <td colspan="2" align="center" bgcolor="';
    print $white;
    echo '">
';
    if ((($update_wares != '') && ($factor != 0))) {
        $sql = 'SELECT groups, subgroups, vendor, code_wares, name_wares, partnumber, price, sclad, transit, warranties FROM import WHERE code_wares != 0';
        $sth = mysql_query($sql, $connect_mysql);
        $a = 0;
        $err = 0;
        $tr = 0;
        $table = 0;
        $af = 0;
        while ($hash_ref = mysql_fetch_row($sth)) {
            $groups = $hash_ref[0];
            $subgroup = $hash_ref[1];
            $vendor = $hash_ref[2];
            $code_wares = $hash_ref[3];
            $name_wares = $hash_ref[4];
            $partnumber = $hash_ref[5];
            $price = $hash_ref[6];
            $sclad = $hash_ref[7];
            $transit = $hash_ref[8];
            $warranties = $hash_ref[9];
            $sclad = ($sclad + $transit);
            $factor = ereg_replace(',', '.', $factor);
            $price = ($price * $factor);
            $price = sprintf('%.1f', $price);
            $sql3 = 'SELECT code_wares FROM wares WHERE code_wares= \'' . $code_wares . '\'';
            $sth3 = mysql_query($sql3);
            $hash_ref3 = mysql_fetch_row($sth3);
            if (($hash_ref3[0] == '')) {
                if (($table == 0)) {
                    echo '	 <table width=100% border=0 cellspacing=2 cellpadding=3>
    <tr>
	 <td colspan="8" bgcolor="';
                    print $color_1;
                    echo '"><font color="';
                    print $white;
                    echo '">ДОБАВЛЕННЫ НОВЫЕ ТОВАРЫ</font></td>
	</tr>
	<tr>
	 <td align="center" valign="bottom" width="40" bgcolor="';
                    print $color_4;
                    echo '"><img src="img/code_wares.gif" width="15" height="71" alt="" border="0"></td>
	 <td valign="bottom" bgcolor="';
                    print $color_4;
                    echo '" width="80" align="center"><img src="img/vendor.gif" width="16" height="94" alt="" border="0"></td>
	 <td valign="bottom" bgcolor="';
                    print $color_4;
                    echo '" align="center"><img src="img/name_wares.gif" width="13" height="132" alt="" border="0"></td>
	 <td valign="bottom" bgcolor="';
                    print $color_4;
                    echo '" width="30" align="center"><img src="img/part_number.gif" width="12" height="74" alt="" border="0"></td>
	 <td valign="bottom" bgcolor="';
                    print $color_4;
                    echo '" align="center"><img src="img/price.gif" width="13" height="33" alt="" border="0"></td>
 	 <td valign="bottom" bgcolor="';
                    print $color_4;
                    echo '" width="30" align="center"><img src="img/sclad.gif" width="14" height="64" alt="" border="0"></td>
 	 <td valign="bottom">&nbsp;</td>
    </tr>
	 ';
                    $table = 1;
                }
                echo '	<tr>
	 <td width="40" valign="baseline">';
                print $code_wares;
                echo '</td>
	 <td bgcolor="';
                print $color_4;
                echo '" width="80">';
                print $vendor;
                echo '</td>
	 <td >';
                print $name_wares;
                echo '</td>
	 <td bgcolor="';
                print $color_4;
                echo '" width="30">';
                print $partnumber;
                echo '</td>
	 <td width="30">';
                print $price;
                echo '</td>
 	 <td bgcolor="';
                print $color_4;
                echo '" width="30">';
                print $sclad;
                echo '</td>
 	 <td>&nbsp;</td>
	</tr>
   ';
                $sql5 = 'SELECT id_vendor FROM vendors WHERE name_vendor = \'' . $vendor . '\'';
                $sth5 = mysql_query($sql5);
                $hash_ref5 = mysql_fetch_row($sth5);
                $id_vendor = $hash_ref5[0];
                if (($id_vendor == '')) {
                    $sql6 = 'INSERT INTO vendors SET name_vendor = \'' . $vendor . '\'';
                    $sth6 = mysql_query($sql6);
                    $sql7 = 'SELECT max(`id_vendor`) FROM `vendors`';
                    $sth7 = mysql_query($sql7);
                    $hash_ref7 = mysql_fetch_row($sth7);
                    $id_vendor = $hash_ref7[0];
                }
                $sql4 = 'INSERT INTO wares SET
   partnumber = \'' . $partnumber . '\',
   code_wares = \'' . $code_wares . '\',
   name_wares = \'' . $name_wares . '\',
   visibility = \'1\',
   amount = \'' . $sclad . '\',
   price = \'' . $price . '\',
   warranties = \'' . $warranties . '\',
   id_vendor = ' . $id_vendor . ' 
   ';
                $sth4 = mysql_query($sql4);
            }
            $sql1 = 'UPDATE wares SET
  price = \'' . $price . '\',
  amount = \'' . $sclad . '\',
  warranties = \'' . $warranties . '\'
  WHERE code_wares = \'' . $code_wares . '\'
  ';
            $sth1 = mysql_query($sql1);
            $affected_rows = mysql_affected_rows();
            if (($affected_rows != 0)) {
                ++$af;
            }
            if ((mysql_errno() != 0)) {
                print $sth1;
                print (((('<br>Ошибка номер<b>' . mysql_errno()) . ': </b>') . mysql_error()) . '<BR>');
                print ($sql1 . '<br>');
                ++$err;
            }
            ++$a;
        }
        if (($table == 1)) {
            echo '   </table>
   ';
        }
        print '<br><br>Произведены изменения в <b>' . $af . '</b> строках(е)<br>';
        $sql3 = 'UPDATE wares SET visibility = \'1\'
  WHERE price <> \'0\' AND amount <> \'0\'
  ';
        $sth3 = mysql_query($sql3);
        $affected_rows = mysql_affected_rows();
        print 'Добавлены в видимые <b>' . $affected_rows . '</b> позиций(я)';
        if (($del_temp != '')) {
            unlink('upload/datafile.csv');
            $sql2 = 'DELETE FROM import';
            $sth2 = mysql_query($sql2);
            echo '   <meta http-equiv="Refresh" content="0; URL=index.php?file=import"></meta>
   ';
        }
    } else {
        echo '   Импортирование требует ресурсов от сервера и
  в зависимости от размера импортируемого файла может длиться от 5 до 30 секунд.
';
    }
    echo ' </td>
</tr>

</table>
<br><br><br><br>




';
    if (($admin == 'supervisor')) {
        if (($import_groups != '')) {
            $sql = 'DELETE FROM `groups`';
            $sth = mysql_query($sql, $connect_mysql);
            $sql = 'SELECT groups FROM `import` GROUP BY groups';
            $sth = mysql_query($sql, $connect_mysql);
            while ($hash_ref = mysql_fetch_row($sth)) {
                $name_groups = $hash_ref[0];
                $name_groups = ereg_replace('"', '&quot;', $name_groups);
                $sql1 = 'INSERT INTO groups SET name_groups = \'' . $name_groups . '\'';
                $sth1 = mysql_query($sql1);
                echo (((('<b>' . mysql_errno()) . ': ') . mysql_error()) . '</b><BR>');
                print ($sql1 . '<br><br>');
            }
            $sql = 'SELECT id_groups, name_groups FROM `groups`';
            $sth = mysql_query($sql, $connect_mysql);
            while ($hash_ref = mysql_fetch_row($sth)) {
                $id_groups = $hash_ref[0];
                $name_groups = $hash_ref[1];
                print ((($id_groups . '-') . $name_groups) . '<br>');
                $sql1 = 'SELECT subgroups
  FROM `import`
  WHERE groups = \'' . $name_groups . '\'
  GROUP By subgroups';
                $sth1 = mysql_query($sql1);
                while ($hash_ref1 = mysql_fetch_row($sth1)) {
                    $sub_groups = $hash_ref1[0];
                    $sub_groups = ereg_replace('"', '&quot;', $sub_groups);
                    $sql2 = 'INSERT INTO groups SET
   name_groups = \'' . $sub_groups . '\',
   belong_groups = \'' . $id_groups . '\'
   ';
                    $sth2 = mysql_query($sql2);
                    echo (((('<b>' . mysql_errno()) . ': ') . mysql_error()) . '</b><BR>');
                    print ($sql2 . '<br><br>');
                }
            }
            $sql = 'DELETE FROM `vendor`';
            $sth = mysql_query($sql, $connect_mysql);
            $sql = 'SELECT vendor
FROM `import`
GROUP BY vendor';
            $sth = mysql_query($sql, $connect_mysql);
            while ($hash_ref = mysql_fetch_row($sth)) {
                $name_vendor = $hash_ref[0];
                $sql1 = 'INSERT INTO vendors SET name_vendor = \'' . $name_vendor . '\'';
                echo (((('<b>' . mysql_errno()) . ': ') . mysql_error()) . '</b><BR>');
                print ($sql1 . '<br>');
                $sth1 = mysql_query($sql1);
            }
        }
        print '
<input type=hidden name=file value=import>
<input type=hidden name=admin value=supervisor>
<input type=submit name=import_groups value="импорт групп и вендоров">
';
        if (($import_wares != '')) {
            $sql = 'SELECT  g.id_groups, g.name_groups,v.id_vendor, i.vendor, i.code_wares, i.name_wares, i.partnumber, i.price, i.sclad, i.transit
FROM import i, groups g ,vendors v
WHERE i.subgroups = g.name_groups AND i.vendor = v.name_vendor
GROUP BY i.code_wares
';
            $a = 1;
            $sth = mysql_query($sql, $connect_mysql);
            while ($hash_ref = mysql_fetch_row($sth)) {
                $id_groups = $hash_ref[0];
                $name_groups = $hash_ref[1];
                $id_vendor = $hash_ref[2];
                $vendor = $hash_ref[3];
                $code_wares = $hash_ref[4];
                $name_wares = $hash_ref[5];
                $partnumber = $hash_ref[6];
                $price = $hash_ref[7];
                $sclad = $hash_ref[8];
                $transit = $hash_ref[9];
                $sclad = ($sclad + $transit);
                $sql1 = 'INSERT INTO wares SET
 partnumber = \'' . $partnumber . '\',
 code_wares = \'' . $code_wares . '\',
 id_vendor = \'' . $id_vendor . '\',
 name_wares = \'' . $name_wares . '\',
 belong_groups = \'' . $id_groups . '\',
 amount = \'' . $sclad . '\',
 price  = \'' . $price . '\',
 visibility = \'1\'
 ';
                $sth1 = mysql_query($sql1);
                echo (((('<b>' . mysql_errno()) . ': ') . mysql_error()) . '</b><BR>');
                print (('<b>' . $a . '</b>' . $sql1) . '<br><br>');
                ++$a;
            }
        }
        print '
<input type=hidden name=file value=import>
<input type=hidden name=admin value=supervisor>
<input type=submit name=import_wares value="импорт_товаров">
';
    }
    return 1;
}

