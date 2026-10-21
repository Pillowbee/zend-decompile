<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
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
