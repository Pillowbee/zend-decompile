<?php
/* EXPERIMENTAL Zend recovery v23. Verify before use. */
$_zend_decompiler_pc_v19 = 'B000';
while (1) {
    switch ($_zend_decompiler_pc_v19) {
        case 'B000':
            check_database($key, $key1, $connect_mysql, $db_name);
            if (($new_user != '')) {
                $_zend_decompiler_pc_v19 = 'B012';
            } else {
                $_zend_decompiler_pc_v19 = 'B088';
            }
            break;
        case 'B012':
            $sql = 'SELECT name_field, descript_field FROM users_field WHERE select_field <> \'\' ORDER BY sort_field';
            $sth = mysql_query($sql, $connect_mysql);
            $reg_new_user = 'yes';
            $_zend_decompiler_pc_v19 = 'B021';
            break;
        case 'B021':
            if (($hash_ref = mysql_fetch_row($sth))) {
                $_zend_decompiler_pc_v19 = 'B027';
            } else {
                $_zend_decompiler_pc_v19 = 'B043';
            }
            break;
        case 'B027':
            $name_field = $hash_ref[0];
            $descript_field = $hash_ref[1];
            if ((${$name_field} == '')) {
                $_zend_decompiler_pc_v19 = 'B034';
            } else {
                $_zend_decompiler_pc_v19 = 'B021';
            }
            break;
        case 'B034':
            $reg_new_user = 'no';
            $error = 'Не набрано обязательное поле <b>' . $descript_field . '</b>';
            return NULL;
        case 'B043':
            if (($password != $password1)) {
                $_zend_decompiler_pc_v19 = 'B045';
            } else {
                $_zend_decompiler_pc_v19 = 'B048';
            }
            break;
        case 'B045':
            $reg_new_user = 'no';
            $error = 'Набранные пароли не совпадают';
            return NULL;
        case 'B048':
            if (($reg_new_user == 'yes')) {
                $_zend_decompiler_pc_v19 = 'B050';
            } else {
                $_zend_decompiler_pc_v19 = 'B087';
            }
            break;
        case 'B050':
            $sql_insert = 'INSERT INTO users SET ';
            $sql = 'DESC users';
            $sth = mysql_query($sql, $connect_mysql);
            $n = 0;
            $_zend_decompiler_pc_v19 = 'B060';
            break;
        case 'B060':
            if (($hash_ref = mysql_fetch_assoc($sth))) {
                $_zend_decompiler_pc_v19 = 'B066';
            } else {
                $_zend_decompiler_pc_v19 = 'B078';
            }
            break;
        case 'B066':
            if (($n != 0)) {
                $_zend_decompiler_pc_v19 = 'B068';
            } else {
                $_zend_decompiler_pc_v19 = 'B069';
            }
            break;
        case 'B068':
            $sql_insert .= ', ';
            $_zend_decompiler_pc_v19 = 'B069';
            break;
        case 'B069':
            $sql_insert .= ((($hash_ref['Field'] . ' = \'') . ${$hash_ref['Field']}) . '\'');
            ++$n;
            $_zend_decompiler_pc_v19 = 'B060';
            break;
        case 'B078':
            $sth = mysql_query($sql_insert, $connect_mysql);
            $old_user = '1';
            $_zend_decompiler_pc_v19 = 'B088';
            break;
        case 'B087':
            $error = 'Новая регистрация не произведена, проверте правильность<br>
  заполнения полей.
  ';
            $_zend_decompiler_pc_v19 = 'B088';
            break;
        case 'B088':
            if (($old_user != '')) {
                $_zend_decompiler_pc_v19 = 'B090';
            } else {
                $_zend_decompiler_pc_v19 = 'B158';
            }
            break;
        case 'B090':
            if ((($password != '') && ($email_user != ''))) {
                $_zend_decompiler_pc_v19 = 'B095';
            } else {
                $_zend_decompiler_pc_v19 = 'B158';
            }
            break;
        case 'B095':
            $sql = 'SELECT id_user FROM users WHERE email_user = \'' . $email_user . '\' and password = \'' . $password . '\'';
            $sth = mysql_query($sql, $connect_mysql);
            $href = mysql_fetch_row($sth);
            $id_user = $href[0];
            if (($id_user != '')) {
                $_zend_decompiler_pc_v19 = 'B118';
            } else {
                $_zend_decompiler_pc_v19 = 'B144';
            }
            break;
        case 'B118':
            if (($metod_auth == 'session')) {
                $_zend_decompiler_pc_v19 = 'B120';
            } else {
                $_zend_decompiler_pc_v19 = 'B132';
            }
            break;
        case 'B120':
            session_name('user');
            session_start();
            session_register(id_session);
            $id_session = $id_user;
            $id_session_temp = $id_user;
            $_zend_decompiler_pc_v19 = 'B158';
            break;
        case 'B132':
            if (($metod_auth == 'cookie')) {
                $_zend_decompiler_pc_v19 = 'B134';
            } else {
                $_zend_decompiler_pc_v19 = 'B142';
            }
            break;
        case 'B134':
            $id_session_temp = $id_user;
            setcookie('id_session', $id_user);
            $_zend_decompiler_pc_v19 = 'B158';
            break;
        case 'B142':
            $id_session_temp = '';
            $_zend_decompiler_pc_v19 = 'B158';
            break;
        case 'B144':
            $id_session_temp = '';
            if (($recall_mail == '')) {
                $_zend_decompiler_pc_v19 = 'B147';
            } else {
                $_zend_decompiler_pc_v19 = 'B158';
            }
            break;
        case 'B147':
            $error = 'Неправильно набран Email или Пароль.
    <table width=100% border=0 cellpadding=5 cellspacing=2><tr>
	 <td bgcolor=' . $color_4 . '>Забыли пароль? Наберите Email с которым регистрировались на нашем сайте.
	 На него будет отослан пароль.
	 </td>
     <td bgcolor=' . $color_4 . '><input type=text name=recall_mail value=@></td>
	 <td bgcolor=' . $color_4 . '><input type=submit value=ok></td>
    </tr>
    </table>';
            $_zend_decompiler_pc_v19 = 'B158';
            break;
        case 'B158':
            if (($metod_auth == 'session')) {
                $_zend_decompiler_pc_v19 = 'B160';
            } else {
                $_zend_decompiler_pc_v19 = 'B164';
            }
            break;
        case 'B160':
            $id_session_auth = $HTTP_SESSION_VARS[id_session];
            $_zend_decompiler_pc_v19 = 'B171';
            break;
        case 'B164':
            if (($metod_auth == 'cookie')) {
                $_zend_decompiler_pc_v19 = 'B166';
            } else {
                $_zend_decompiler_pc_v19 = 'B170';
            }
            break;
        case 'B166':
            $id_session_auth = $HTTP_COOKIE_VARS[id_session];
            $_zend_decompiler_pc_v19 = 'B171';
            break;
        case 'B170':
            $id_session_auth = '';
            $_zend_decompiler_pc_v19 = 'B171';
            break;
        case 'B171':
            if ((($id_session_auth == '') && ($id_session_temp != ''))) {
                $_zend_decompiler_pc_v19 = 'B176';
            } else {
                $_zend_decompiler_pc_v19 = 'B177';
            }
            break;
        case 'B176':
            $id_session_auth = $id_session_temp;
            $_zend_decompiler_pc_v19 = 'B177';
            break;
        case 'B177':
            if ((($id_auth_page == '1') && ($id_users != ''))) {
                $_zend_decompiler_pc_v19 = 'B182';
            } else {
                $_zend_decompiler_pc_v19 = 'B183';
            }
            break;
        case 'B182':
            $id_session_auth = $id_users;
            $_zend_decompiler_pc_v19 = 'B183';
            break;
        case 'B183':
            if (($recall_mail != '')) {
                $_zend_decompiler_pc_v19 = 'B185';
            } else {
                $_zend_decompiler_pc_v19 = 'B258';
            }
            break;
        case 'B185':
            $sql = 'SELECT id_user, name_user,  password, email_user  FROM users WHERE email_user = \'' . $recall_mail . '\'';
            $sth = mysql_query($sql, $connect_mysql);
            $href = mysql_fetch_row($sth);
            $id_user = $href[0];
            $name_user_mail = $href[1];
            $password_user_mail = $href[2];
            $email_user_mail = $href[3];
            if (($id_user != '')) {
                $_zend_decompiler_pc_v19 = 'B212';
            } else {
                $_zend_decompiler_pc_v19 = 'B257';
            }
            break;
        case 'B212':
            $mess .= 'Уважаемый(ая): ' . $name_user_mail . '
';
            $mess .= 'Вы зарегистрировались в интернет магазине ' . $supplier_name . '
';
            $mess .= 'Для входа используйте:
';
            $mess .= 'Email - ' . $email_user_mail . '
';
            $mess .= 'Password - ' . $password_user_mail . '
';
            $headers = 'From: ' . $supplier_name . ' <' . $supplier_email . '>
';
            $headers .= 'X-Priority: 1
';
            $headers .= 'Content-Type: text/plain; charset=windows-1251
';
            mail($email_user_mail, 'Вы зарегистрировались в интернет магазине ' . $supplier_name, $mess, $headers);
            $error = 'Пароль отослан на зарегестрированный Email';
            $_zend_decompiler_pc_v19 = 'B258';
            break;
        case 'B257':
            $error = 'Не зарегестрированный Email';
            $_zend_decompiler_pc_v19 = 'B258';
            break;
        case 'B258':
            if (($id_auth_page == 1)) {
                $_zend_decompiler_pc_v19 = 'B260';
            } else {
                $_zend_decompiler_pc_v19 = 'B263';
            }
            break;
        case 'B260':
            $auth_user_admin = '';
            $auth_path_admin = '../';
            $_zend_decompiler_pc_v19 = 'B265';
            break;
        case 'B263':
            $auth_user_admin = '';
            $auth_path_admin = '';
            $_zend_decompiler_pc_v19 = 'B265';
            break;
        case 'B265':
            if (($HTTP_COOKIE_VARS['id_sess'] == '')) {
                $_zend_decompiler_pc_v19 = 'B268';
            } else {
                $_zend_decompiler_pc_v19 = 'B279';
            }
            break;
        case 'B268':
            $rand_keys_sess = rand_keys();
            setcookie('id_sess', $rand_keys_sess, 1, '/');
            $_zend_decompiler_pc_v19 = 'B281';
            break;
        case 'B279':
            $rand_keys_sess = $HTTP_COOKIE_VARS['id_sess'];
            $_zend_decompiler_pc_v19 = 'B281';
            break;
        case 'B281':
            return 1;
        default:
            trigger_error('Invalid recovered control-flow state', E_USER_ERROR);
            return NULL;
    }
}
