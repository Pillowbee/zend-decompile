<?php
/* EXPERIMENTAL function fragment, not complete fun_all.php. */
function link_is_present($url) {
    global $supplier_url;
    $url_file = ('http://' . $url);
    $fp = @file($url_file);
    if (is_array($fp)) {
        $content_page = implode(' ', $fp);
    }
    if (stristr($content_page, ('<a href="http://' . $supplier_url))) {
        $string = 'есть';
    } else {
        $string = 'нет';
    }
    return $string;
    
}
