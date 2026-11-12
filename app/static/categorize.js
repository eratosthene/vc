// The Categorize list's edit modal. Without this script, or if a request here
// fails, the edit buttons are plain links to the edit page.
(function () {
    "use strict";

    var $modal = $("#categorize-modal");
    var $body = $modal.find(".modal-body");
    var $save = $("#categorize-save");
    var $editing = null; // the row being edited
    var fallbackUrl = null; // the stock edit page for it

    function showForm(html) {
        $body.html(html);
        $body.find(".my_select2").select2({
            placeholder: "Select a State",
            allowClear: true,
            theme: "bootstrap",
            dropdownParent: $modal,
        });
    }

    // Anything we can't handle here goes to the stock edit page.
    function fallBack() {
        window.location.href = fallbackUrl;
    }

    $(document).on("click", "tr[data-modal-url] a[href*='/edit/']", function (e) {
        // Let a modified click (new tab) do its usual thing.
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.which > 1) {
            return;
        }
        e.preventDefault();
        var $row = $(this).closest("tr");
        $editing = $row;
        fallbackUrl = this.href;
        $.get($row.data("modal-url"))
            .done(function (html) {
                showForm(html);
                $save.prop("disabled", false);
                $modal.modal("show");
            })
            .fail(fallBack);
    });

    $modal.on("submit", "form", function (e) {
        e.preventDefault();
        $save.prop("disabled", true);
        var $row = $editing;
        $.ajax({
            url: $row.data("modal-url"),
            method: "POST",
            data: $(this).serialize(),
        })
            .done(function (html) {
                var $new = $($.parseHTML($.trim(html))).filter("tr");
                $row.replaceWith($new);
                $modal.modal("hide");
            })
            .fail(function (xhr) {
                if (xhr.status === 422) {
                    showForm(xhr.responseText);
                    $save.prop("disabled", false);
                } else {
                    fallBack();
                }
            });
    });
})();
