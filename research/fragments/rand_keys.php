<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
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
