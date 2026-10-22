<?php
/* EXPERIMENTAL Zend recovery v29. Verify before use. */
if (($link_n == 0)) {
    $link_n = '';
}
if (('' != $link_n)) {
    $sql = 'SELECT name_link, file_link, dir_link FROM
 pages_links WHERE id_link = \'' . $link_n . '\'';
    $qwe = mysql_query($sql, $connect_mysql);
    $rs1 = mysql_fetch_row($qwe);
    $name_section = $rs1[0];
    $file_section = $rs1[1];
    $dir_section = $rs1[2];
}
if (($dir_section == '')) {
    $dir_section = 'include';
}
if ((($page == '') || ($page == '0'))) {
    $page = 1;
    $page_forum = 0;
    $page_wares = 0;
    $page_wares_admin = 0;
    $page_news = 0;
    $page_user = 0;
    $page_order = 0;
    $page_mess = 0;
    $page_link = 0;
} else {
    $page_forum = (($page - 1) * $lines_forum);
    $page_wares = (($page - 1) * $lines_wares);
    $page_wares_admin = (($page - 1) * $lines_wares_admin);
    $page_news = (($page - 1) * $lines_news);
    $page_user = (($page - 1) * $lines_user);
    $page_order = (($page - 1) * $lines_order);
    $page_mess = (($page - 1) * $lines_mess);
    $page_link = (($page - 1) * $lines_link);
}
if (($HTTP_GET_VARS['partner'] != '')) {
    setcookie('partner', $HTTP_GET_VARS['partner'], 0, '/');
}
return 1;


function out_link($url) {
    global $connect_mysql;
    global $REQUEST_URI;
    global $old_search;
    if (((strstr($REQUEST_URI, 'htm') == '') && ($old_search != 'y'))) {
        print $url;
    } else {
        $array_url = parse_url($url);
        parse_str($array_url[query], $array_url_str);
        $array_key = array_keys($array_url_str);
        $array_value = array_values($array_url_str);
        $count = count($array_key);
        $string_url = '';
        $a = 0;
        while ($a < count($array_key)) {
            if (($array_value[$a] != '')) {
                $string_url .= ((($array_key[$a] . '/') . $array_value[$a]) . '/');
            }
            ++$a;
        }
        $string_url .= '';
        print (url_prefix() . $string_url);
    }
    return NULL;
    
}

function currency_type($currency, $CurTypeID, $text_key) {
    if ((($CurTypeID[$text_key] == 0) || ($CurTypeID[$text_key] == ''))) {
        $currency_type = '-?-';
    } else {
        $currency_type = $currency[$CurTypeID[$text_key]]['cur_type'];
    }
    return $currency_type;
    
}

function out_price($price, $currency, $CurTypeID, $text_key, $currency_key) {
    global $connect_mysql;
    global $count_sign_default;
    $numargs = func_num_args();
    $arg_list = func_get_args();
    if (($arg_list[5] == '')) {
        $not_out_type = currency_type($currency, $CurTypeID, $text_key);
    } else {
        $not_out_type = '';
    }
    if (($arg_list[6] == '')) {
        $count_num = $count_sign_default;
    } else {
        $count_num = $arg_list[6];
    }
    $course_temp = $currency[$CurTypeID['admin']][$currency_key];
    if ((($text_key == 'user') || ($text_key == 'basket') || ($text_key == 'national'))) {
        $course_temp1 = $currency[$CurTypeID[$text_key]][$currency_key];
    }
    if (($text_key == 'admin')) {
        $course_temp = 1;
        $course_temp1 = 1;
    }
    if ((($text_key != 'user') && ($text_key != 'basket') && ($text_key != 'national') && ($text_key != 'admin'))) {
        foreach ($currency as &$row) {
            if (($row['cur_ticker'] == $text_key)) {
                $course_temp1 = $currency[$row['id']][$currency_key];
                $CurTypeID[$text_key] = $row['id'];
            }
        }
    }
    if (($course_temp1 == 0)) {
        $course_temp = 1;
        $course_temp1 = 1;
        $CurTypeID[$text_key] = 0;
    }
    $price = round((($price * $course_temp) / $course_temp1), $count_num);
    if (($arg_list[5] == '')) {
        if (($currency[$CurTypeID[$text_key]]['position'] == 1)) {
            $price = ((currency_type($currency, $CurTypeID, $text_key) . '') . $price);
        } else {
            $price = (($price . '&nbsp;') . currency_type($currency, $CurTypeID, $text_key));
        }
    }
    return $price;
    
}

function uc_rus($s) {
    $r = '';
    $s = chunk_split($s, 1, '#');
    $ar = explode('#', $s);
    foreach ($ar as &$c) {
        $x = ord($c);
        if (((97 <= $x) && ($x <= 122))) {
            $x = ($x - 32);
        }
        if (((224 <= $x) && ($x <= 255))) {
            $x = ($x - 32);
        }
        $r = ($r . chr($x));
    }
    return $r;
    
}

function path_groups($number_groups) {
    global $connect_mysql;
    global $file;
    global $page;
    global $id_vendor;
    global $sg_wares;
    global $sg_desk;
    echo '<a class="$Tgroups_st" href=';
    out_link('index.php?link_n=' . $link_n . '&file=' . $file . '&page=' . $page . '&sg_wares=' . $sg_wares . '&sg_desk=' . $sg_desk);
    echo '>ПРОДУКЦИЯ</a>&nbsp;<font class="AdminFont">/</font>
';
    $n = 0;
    while ($number_groups != 0) {
        $statement = 'SELECT id_groups, belong_groups, name_groups FROM groups WHERE id_groups = \'' . $number_groups . '\'';
        $sth = mysql_query($statement);
        $aref = mysql_fetch_row($sth);
        $id_belong_groups = $aref[0];
        $number_groups = $aref[1];
        $name_groups = $aref[2];
        $array_name[$n] = $name_groups;
        $array_number[$n] = $id_belong_groups;
        ++$n;
    }
    if (($array_number[0] != '')) {
        $n = 0;
        $a_number = array_reverse($array_number);
        $a_name = array_reverse($array_name);
        while ($array_number[$n] != '') {
            global $connect_mysql;
            global $file;
            global $n_page;
            global $id_vendor;
            global $sg_wares;
            global $sg_desk;
            if (($file != '')) {
                $file_p = '&file=';
            }
            if (($n == (count($a_name) - 1))) {
                $a_name[$n] = (('<b>' . $a_name[$n]) . '</b>');
            }
            echo '<a class="$Tgroups_st" href=';
            out_link('index.php?id_groups=' . $a_number[$n] . $file_p . $file . '&page=' . $page . '&id_vendor=' . $id_vendor . '&sg_wares=' . $sg_wares . '&sg_desk=' . $sg_desk);
            echo '>';
            print $a_name[$n];
            echo '</a>&nbsp;<font class="AdminFont">/</font>
 ';
            ++$n;
        }
    }
    return NULL;
    
}

function page_links_out($sql_page_links, $lines) {
    $_zend_decompiler_pc_v19 = 'B000';
    while (1) {
        switch ($_zend_decompiler_pc_v19) {
            case 'B000':
                global $connect_mysql;
                global $HTTP_POST_VARS;
                global $HTTP_GET_VARS;
                global $array_variable;
                global $page_links_down;
                global $page;
                global $n_page;
                global $select;
                global $ls_pg;
                $listing_pg = 5;
                echo '<table border="0" cellspacing="2" cellpadding="0">
<tr>
<td>
';
                if ((count($HTTP_POST_VARS) != 0)) {
                    $_zend_decompiler_pc_v19 = 'B028';
                } else {
                    $_zend_decompiler_pc_v19 = 'B029';
                }
                break;
            case 'B028':
                $array_var_temp = $HTTP_POST_VARS;
                $_zend_decompiler_pc_v19 = 'B029';
                break;
            case 'B029':
                if ((count($HTTP_GET_VARS) != 0)) {
                    $_zend_decompiler_pc_v19 = 'B035';
                } else {
                    $_zend_decompiler_pc_v19 = 'B036';
                }
                break;
            case 'B035':
                $array_var_temp = $HTTP_GET_VARS;
                $_zend_decompiler_pc_v19 = 'B036';
                break;
            case 'B036':
                if ((count($array_variable) != 0)) {
                    $_zend_decompiler_pc_v19 = 'B042';
                } else {
                    $_zend_decompiler_pc_v19 = 'B043';
                }
                break;
            case 'B042':
                $array_var_temp = $array_variable;
                $_zend_decompiler_pc_v19 = 'B043';
                break;
            case 'B043':
                if ((count($array_var_temp) == 0)) {
                    $_zend_decompiler_pc_v19 = 'B049';
                } else {
                    $_zend_decompiler_pc_v19 = 'B051';
                }
                break;
            case 'B049':
                $array_var_temp = array();
                $_zend_decompiler_pc_v19 = 'B051';
                break;
            case 'B051':
                $sth = mysql_query($sql_page_links);
                $count_id_positions = mysql_num_rows($sth);
                if (($count_id_positions == 0)) {
                    $_zend_decompiler_pc_v19 = 'B063';
                } else {
                    $_zend_decompiler_pc_v19 = 'B067';
                }
                break;
            case 'B063':
                print '</td></tr></table>';
                return NULL;
            case 'B067':
                if (($page_links_down != 1)) {
                    $_zend_decompiler_pc_v19 = 'B069';
                } else {
                    $_zend_decompiler_pc_v19 = 'B076';
                }
                break;
            case 'B069':
                print 'Всего позиций - ' . $count_id_positions . '<br>';
                $page_links_down = 1;
                $_zend_decompiler_pc_v19 = 'B076';
                break;
            case 'B076':
                print 'Перейти на страницу:&nbsp;';
                $d = 0;
                $a_k = array_keys($array_var_temp);
                $a_v = array_values($array_var_temp);
                $d = 0;
                $a = 0;
                $_zend_decompiler_pc_v19 = 'B091';
                break;
            case 'B091':
                if (($a < count($a_k))) {
                    $_zend_decompiler_pc_v19 = 'B099';
                } else {
                    $_zend_decompiler_pc_v19 = 'B120';
                }
                break;
            case 'B097':
                ++$a;
                $_zend_decompiler_pc_v19 = 'B091';
                break;
            case 'B099':
                if ((count($a_v[$a]) != '')) {
                    $_zend_decompiler_pc_v19 = 'B106';
                } else {
                    $_zend_decompiler_pc_v19 = 'B097';
                }
                break;
            case 'B106':
                if (($a_v[$a] != '')) {
                    $_zend_decompiler_pc_v19 = 'B109';
                } else {
                    $_zend_decompiler_pc_v19 = 'B117';
                }
                break;
            case 'B109':
                if (($d != 0)) {
                    $_zend_decompiler_pc_v19 = 'B111';
                } else {
                    $_zend_decompiler_pc_v19 = 'B112';
                }
                break;
            case 'B111':
                $quer_string .= '&';
                $_zend_decompiler_pc_v19 = 'B112';
                break;
            case 'B112':
                $quer_string .= (($a_k[$a] . '=') . $a_v[$a]);
                $_zend_decompiler_pc_v19 = 'B117';
                break;
            case 'B117':
                $d = 1;
                $_zend_decompiler_pc_v19 = 'B097';
                break;
            case 'B120':
                $quer_string = ereg_replace(' ', '%20', $quer_string);
                if (($ls_pg == '')) {
                    $_zend_decompiler_pc_v19 = 'B129';
                } else {
                    $_zend_decompiler_pc_v19 = 'B130';
                }
                break;
            case 'B129':
                $ls_pg = 1;
                $_zend_decompiler_pc_v19 = 'B130';
                break;
            case 'B130':
                $a1 = 0;
                $a = (($listing_pg * $ls_pg) - ($listing_pg - 1));
                $_zend_decompiler_pc_v19 = 'B135';
                break;
            case 'B135':
                if ((($a - 1) < ceil(($count_id_positions / $lines)))) {
                    $_zend_decompiler_pc_v19 = 'B144';
                } else {
                    $_zend_decompiler_pc_v19 = 'B331';
                }
                break;
            case 'B142':
                ++$a;
                $_zend_decompiler_pc_v19 = 'B135';
                break;
            case 'B144':
                if (strstr($quer_string, 'page')) {
                    $_zend_decompiler_pc_v19 = 'B150';
                } else {
                    $_zend_decompiler_pc_v19 = 'B216';
                }
                break;
            case 'B150':
                if (($a != 1)) {
                    $_zend_decompiler_pc_v19 = 'B152';
                } else {
                    $_zend_decompiler_pc_v19 = 'B166';
                }
                break;
            case 'B152':
                $quer_string = ereg_replace('page=' . $page, 'page=' . $a, $quer_string);
                $_zend_decompiler_pc_v19 = 'B218';
                break;
            case 'B166':
                $quer_string = ereg_replace('page=' . $page, '', $quer_string);
                if ((substr($quer_string, -1) == '&')) {
                    $_zend_decompiler_pc_v19 = 'B183';
                } else {
                    $_zend_decompiler_pc_v19 = 'B195';
                }
                break;
            case 'B183':
                $quer_string = substr($quer_string, 0, (strlen($quer_string) - 1));
                $_zend_decompiler_pc_v19 = 'B195';
                break;
            case 'B195':
                if ((substr($quer_string, -1) == '?')) {
                    $_zend_decompiler_pc_v19 = 'B202';
                } else {
                    $_zend_decompiler_pc_v19 = 'B218';
                }
                break;
            case 'B202':
                $quer_string = substr($quer_string, 0, (strlen($quer_string) - 1));
                $_zend_decompiler_pc_v19 = 'B218';
                break;
            case 'B216':
                $quer_string .= ('&page=' . $a);
                $_zend_decompiler_pc_v19 = 'B218';
                break;
            case 'B218':
                if (((1 < $ls_pg) && ($a1 == 0))) {
                    $_zend_decompiler_pc_v19 = 'B223';
                } else {
                    $_zend_decompiler_pc_v19 = 'B265';
                }
                break;
            case 'B223':
                $page_temp = (($listing_pg * $ls_pg) - $listing_pg);
                $page_temp1 = ($page_temp + 1);
                $quer_string_back = ereg_replace('&ls_pg=' . $ls_pg, '', $quer_string);
                $quer_string_back = ereg_replace('page=' . $page_temp1, 'page=' . $page_temp, $quer_string_back);
                $ls_pg_temp = ($ls_pg - 1);
                echo ' <a href=';
                out_link('index.php?' . $quer_string_back . '&ls_pg=' . $ls_pg_temp);
                echo '>';
                echo '<';
                echo '<.....</a>
 ';
                $a1 = 1;
                $_zend_decompiler_pc_v19 = 'B265';
                break;
            case 'B265':
                if ((($listing_pg * $ls_pg) < $a)) {
                    $_zend_decompiler_pc_v19 = 'B268';
                } else {
                    $_zend_decompiler_pc_v19 = 'B293';
                }
                break;
            case 'B268':
                $quer_string = ereg_replace('&ls_pg=' . $ls_pg, '', $quer_string);
                $ls_pg_temp = ($ls_pg + 1);
                echo ' <a href=';
                out_link('index.php?' . $quer_string . '&ls_pg=' . $ls_pg_temp);
                echo '>.....>></a>
 ';
                print '</td></tr></table>';
                return NULL;
            case 'B293':
                echo '  ';
                if (($a == $page)) {
                    $_zend_decompiler_pc_v19 = 'B296';
                } else {
                    $_zend_decompiler_pc_v19 = 'B307';
                }
                break;
            case 'B296':
                print '<font size=2 style="border-bottom-style: inherit; background: ' . $color_light_1 . ';" color=' . $select . '>&nbsp;<b>' . $a . '</b>&nbsp;</font>';
                $_zend_decompiler_pc_v19 = 'B317';
                break;
            case 'B307':
                echo '<a href=';
                out_link('index.php?' . $quer_string);
                echo '>';
                print $a;
                echo '</a>
   ';
                $_zend_decompiler_pc_v19 = 'B317';
                break;
            case 'B317':
                $quer_string = ereg_replace('page=' . $a, 'page=' . $page, $quer_string);
                $_zend_decompiler_pc_v19 = 'B142';
                break;
            case 'B331':
                echo '</td>
</tr>
</table>
';
                return NULL;
            default:
                trigger_error('Invalid recovered control-flow state', E_USER_ERROR);
                return NULL;
        }
    }
}

function url_prefix() {
    global $connect_mysql;
    global $old_search;
    global $id_auth_page;
    $numargs = func_num_args();
    if (($old_search == 'y')) {
        if (($numargs != 0)) {
            return '';
        } else {
            return '/';
        }
    } else {
        if (($id_auth_page == 1)) {
            return '../';
        } else {
            return '';
        }
    }
    
}

function sort_default($id_sort) {
    global $connect_mysql;
    $sql = 'SELECT name_col_def, direction_sort FROM sort_default WHERE id_sort = \'' . $id_sort . '\'';
    $sth = mysql_query($sql, $connect_mysql);
    $hash_ref = mysql_fetch_row($sth);
    $name_col_def = $hash_ref[0];
    $direction_sort = $hash_ref[1];
    $string_order = (($name_col_def . ' ') . $direction_sort);
    if (($name_col_def == '')) {
        $string_order = '\'\'';
    }
    return $string_order;
    
}

function out_field($area_table) {
    $sql1 = 'SELECT name_field, descript_field FROM users_field WHERE visibility = \'1\' and area_table = \'' . $area_table . '\' ORDER BY sort_field ';
    $sth1 = mysql_query($sql1);
    while ($hash_ref1 = mysql_fetch_row($sth1)) {
        $name_field = $hash_ref1[0];
        $descript_field = $hash_ref1[1];
        global $connect_mysql;
        $$name_field = &$$name_field;
        if ((($name_field != '') && ($name_field != 'нет'))) {
            $mess .= (('<b>' . $descript_field . '</b> - ' . ${$name_field}) . '<br>');
        }
    }
    $mess .= '<br>';
    return $mess;
    
}

function output_button($payment_id) {
    global $connect_mysql;
    global $id_orders;
    global $id_auth_page;
    global $supplier_url;
    $stm5 = 'SELECT see_bill, name_button FROM payments WHERE payment_id = ' . $payment_id;
    $sth5 = mysql_query($stm5);
    $hash_ref5 = mysql_fetch_row($sth5);
    $see_bill = $hash_ref5[0];
    $name_button = $hash_ref5[1];
    if (($see_bill == 1)) {
        if (($id_auth_page == 1)) {
            $original = 1;
        } else {
            $original = 0;
        }
        echo '  ';
        echo '<s';
        echo 'cript language="JavaScript">
  function newWin()
  {
  setCookie(\'id_orders\',';
        print $id_orders;
        echo ',"",\'/\');
  Win = window.open("http://';
        print $supplier_url;
        echo '/cover.php?name=bill&original=';
        print $original;
        echo '&payment_id=';
        print $payment_id;
        echo '","Win",\'toolbar=0,location=0,directories=0,status=0,menubar=1,scrollbars=1,resizable=1,width=680,height=480\');
  }
  </script>
  <input type="button" value="';
        print $name_button;
        echo '" onClick="newWin()"><br>

';
    } else {
        print '&nbsp;';
    }
    return NULL;
    
}

function mail_hide($email, $attribute) {
    if (($email != '')) {
        $array_mail = explode('@', $email);
        $name_mail = $array_mail[0];
        $domain_mail = $array_mail[1];
        if (($attribute == 'text')) {
            echo '  <a href="#" onClick="window.open(\'';
            print url_prefix();
            echo 'cover.php?name=mail_out&name_mail=';
            print $name_mail;
            echo '&domain_mail=';
            print $domain_mail;
            echo '\',\'mail_out\',\'resizable=yes,top=20,left=40,width=300,height=150,location=no,status=no,scrollbars=yes\');return false;">
';
            print $name_mail;
            echo '<img src="';
            print url_prefix();
            echo 'images/mail_@.gif" alt="" width="8" height="9" hspace="2" border="0">';
            print $domain_mail;
            echo '  </a>
  ';
        } else {
            if (($attribute == 'img')) {
                echo '  <a href="#" onClick="window.open(\'';
                print url_prefix();
                echo 'cover.php?name=mail_out&name_mail=';
                print $name_mail;
                echo '&domain_mail=';
                print $domain_mail;
                echo '\',\'mail_out\',\'resizable=yes,top=20,left=40,width=300,height=150,location=no,status=no,scrollbars=yes\');return false;">
  <img src="';
                print $auth_path_admin;
                echo 'images/mail.gif" width="20" height="12" alt="" border="0">
  </a>
  ';
            }
        }
    }
    return NULL;
    
}

function partner_view($name_set) {
    global $connect_mysql;
    $sql = 'SELECT value_set FROM setup WHERE name_set = \'' . $name_set . '\'';
    $sth = mysql_query($sql, $connect_mysql);
    $row = mysql_fetch_assoc($sth);
    if (($row['value_set'] != '0')) {
        return $row['value_set'];
    } else {
        return NULL;
    }
    
}

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

function out_replace_teg($s) {
    $s = eregi_replace('\\[url=', '<a href=', $s);
    $s = eregi_replace('\\[/url]', '</a>', $s);
    $s = eregi_replace('\\[b]', '<b>', $s);
    $s = eregi_replace('\\[/b]', '</b>', $s);
    $s = eregi_replace('\\[i]', '<i>', $s);
    $s = eregi_replace('\\[/i]', '</i>', $s);
    $s = eregi_replace('\\[color=', '<font color=', $s);
    $s = eregi_replace('\\[/color]', '</font>', $s);
    $s = eregi_replace('\\[li]', '<li>', $s);
    $s = eregi_replace('\\[br]', '<br>', $s);
    $point = (((('<img src=' . url_prefix()) . 'images/pynkt.gif width=4 height=7 alt="') . out_alt()) . '" hspace=5 border=0>');
    $s = eregi_replace('\\[point]', $point, $s);
    $s = eregi_replace('\\]', '>', $s);
    return $s;
    
}

function out_replace_files($filename) {
    $handle = fopen($filename, 'r');
    if ((filesize($filename) == '0')) {
        $filesize = 1;
    } else {
        $filesize = filesize($filename);
    }
    $content_file = fread($handle, $filesize);
    fclose($handle);
    $content_file = out_replace_teg($content_file);
    print $content_file;
    return NULL;
    
}

function rand_keys() {
    $array_1 = array('1', 'q', '2', 'w', '3', 'e', '4', 'r', '5', 't', '6', 'y', '7', 'u', '8', 'i', '9', 'o', '0', 'p', 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'z', 'x', 'c', 'v', 'b', 'n', 'm');
    $n = 10;
    $string_rand = '';
    $array_key = array_rand($array_1, $n);
    $a = 0;
    while ($a < $n) {
        $string_rand .= $array_1[$array_key[$a]];
        ++$a;
    }
    return md5(($string_rand . time()));
    
}

function out_alt() {
    global $connect_mysql;
    global $out_name_title;
    $out_name_title = ltrim($out_name_title);
    return $out_name_title;
    
}

function news_name_out($id_section) {
    global $connect_mysql;
    $sql = 'SELECT name_section FROM news_section WHERE id_section = \'' . $id_section . '\' AND visibility = 1';
    $sth = mysql_query($sql, $connect_mysql);
    $hash_ref = mysql_fetch_row($sth);
    $name_section = $hash_ref[0];
    return $name_section;
    
}

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

function minmax_price($id_groups) {
    global $connect_mysql;
    global $select;
    global $currency;
    global $CurTypeID;
    $str_temp2 = (count_wares($id_groups, 0) . $id_groups);
    $sql = 'SELECT min(price), max(price) FROM wares WHERE belong_groups in (' . $str_temp2 . ')';
    $sth = mysql_query($sql, $connect_mysql);
    $hash_ref = mysql_fetch_row($sth);
    $min = $hash_ref[0];
    $max = $hash_ref[1];
    if (($min == $max)) {
        echo 'Цена в группе <font color="';
        print $select;
        echo '">';
        print out_price($min, $currency, $CurTypeID, 'user', 'cur_rate_nal');
        echo '</font>
';
    } else {
        echo 'Цены в группе<br>от <font color="';
        print $select;
        echo '">';
        print out_price($min, $currency, $CurTypeID, 'user', 'cur_rate_nal');
        echo '</font> до <font color="';
        print $select;
        echo '">';
        print out_price($max, $currency, $CurTypeID, 'user', 'cur_rate_nal');
        echo '</font>
 ';
    }
    return NULL;
    
}

function user_discount($id_user) {
    global $connect_mysql;
    global $user_discount;
    global $RateDiscount;
    global $RatePercent;
    global $ReceptionDiscount;
    global $MaxRateDiscount;
    if (is_array($user_discount)) {
        return $user_discount;
    } else {
        if (($id_user != '')) {
            $user_discount = array();
            $sql = 'SELECT id_user, name_user, s_name_user, o_name_user, pers_discount , SUM(o.sum_all) as sum_all
  FROM `users` u LEFT JOIN orders o ON u.id_user=o.id_users
  WHERE  id_user=\'' . $id_user . '\' AND status_id = \'4\' GROUP BY id_user';
            $sth = mysql_query($sql, $connect_mysql);
            $row = mysql_fetch_assoc($sth);
            if (($row['id_user'] == '')) {
                $sql = 'SELECT name_user, s_name_user, o_name_user, pers_discount FROM `users` WHERE  id_user=\'' . $id_user . '\'';
                $sth = mysql_query($sql, $connect_mysql);
                $row = mysql_fetch_assoc($sth);
                $user_discount['accum_sum'] = 0;
                $user_discount['accum_discount'] = 0;
                $user_discount['pers_discount'] = $row['pers_discount'];
            } else {
                $user_discount['pers_discount'] = $row['pers_discount'];
                $user_discount['accum_sum'] = $row['sum_all'];
                $user_discount['accum_discount'] = (floor(($user_discount['accum_sum'] / $RateDiscount)) * $RatePercent);
            }
            $user_discount['name'] = (((($row['s_name_user'] . ' ') . $row['name_user']) . ' ') . $row['o_name_user']);
            if (($MaxRateDiscount < $user_discount['accum_discount'])) {
                $user_discount['accum_discount'] = $MaxRateDiscount;
            }
            if ((strtoupper($ReceptionDiscount) == 'MAX')) {
                $user_discount['all_discount'] = max($user_discount['pers_discount'], $user_discount['accum_discount']);
            } else {
                if ((strtoupper($ReceptionDiscount) == 'SUM')) {
                    $user_discount['all_discount'] = ($user_discount['pers_discount'] + $user_discount['accum_discount']);
                }
            }
        } else {
            $user_discount['pers_discount'] = 'нужна регистрация';
            $user_discount['accum_discount'] = 'нужна регистрация';
            $user_discount['all_discount'] = 'нужна регистрация';
        }
        return $user_discount;
    }
    
}
