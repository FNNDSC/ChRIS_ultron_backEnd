
(function($) {
    'use strict';
    $(document).ready(function() {
        $("#id_url").change( function() { $("#id_name, #id_version").val(""); } );
        $("#id_name, #id_version").change( function() { $("#id_url").val(""); } );
    });
})(django.jQuery);
