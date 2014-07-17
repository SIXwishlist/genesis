var Genesis;

var warning_button_id;
var isProcessing;
var timedAlerts;

Genesis = (function() {
    var firstPasswordEntry = true;

    return {
        query: function (_uri, _data, _noupdate) {
            $.ajax({
                url: _uri,
                data: _data,
                contentType: false,
                processData: false,
                success: _noupdate?undefined:Genesis.Core.processResponse,
                error: Genesis.Core.processOffline,
                type: _data?'POST':'GET',
            });
            firstPasswordEntry = true;
            if (!_noupdate)
                Genesis.UI.showLoader(true);
            return false;
        },

        verify: function(vtype, field1, field2, event){
            var f1 = document.getElementById(field1),
                f2 = document.getElementById(field2),
                match = false;

            if (vtype == 'passwd') {
                if(event.target.id == field1 && firstPasswordEntry) {
                    if (f1.value.length < 6) {
                        var frmgrp = $('#'+field1).parent('.form-group');
                        match = false;
                    } else if (f1.value.length >= 6) {
                        var frmgrp = $('#'+field1).parent('.form-group');
                        match = true;
                    } else {
                        return true;
                    }
                } else {
                    firstPasswordEntry = false;
                    var keycode = (event !== undefined && typeof event.charCode !== "undefined") ? String.fromCharCode(event.charCode) : '';
                    var frmgrp = $('#'+field1+', #'+field2).parent('.form-group');
                    if(event.target.id == field1){
                        match = ((f1.value + (event.keyCode != 13 ? keycode : '') == f2.value) && (f1.value+(event.keyCode != 13 ? keycode : '')).length >= 6);
                    } else {
                        match = ((f1.value == f2.value + (event.keyCode != 13 ? keycode : '')) && (f2.value+(event.keyCode != 13 ? keycode : '')).length >= 6);
                    }
                }
            } else if (vtype == 'user') {
                match = !(RegExp('^$|[A-Z]|\\.|:|[ ]|-$').test(f1.value));
                var frmgrp = $('#'+field1).parent('.form-group');
            } else {
                match = true;
            }

            if (match && frmgrp) {
                frmgrp.removeClass('has-error').addClass('has-success');
                frmgrp.children('.form-control-feedback').removeClass().addClass('form-control-feedback gen-checkmark');
            } else if (!match && frmgrp) {
                frmgrp.removeClass('has-success').addClass('has-error');
                frmgrp.children('.form-control-feedback').removeClass().addClass('form-control-feedback gen-close-2');
            }

            return match;
        },

        submit: function (fid, action) {
            $('.modal').each( function (i, e) {
                Genesis.UI.hideModal(e.id, true);
            });
            Genesis.cancelAuthorization();
            form = $('#'+fid);
            if (form) {
                url = $('input[type=hidden]', form)[0].value;
                var fData = new FormData()
                fData.append('action', action);

                $('input[type=text], input[type=password], input[type=hidden]', form).each(function (i,e) {
                    if (e.name != '__url')
                        fData.append(e.name, e.value);
                });

                $('input[type=checkbox]', form).each(function (i,e) {
                    fData.append(e.name, (e.checked?1:0));
                });

                $('input[type=radio]', form).each(function (i,e) {
                    if (e.checked)
                        fData.append(e.name, e.value);
                });

                $('select:not([id$="-hints"])', form).each(function (i,e) {
                    fData.append(e.name, e.options[e.selectedIndex].value);
                });

                $('textarea', form).each(function (i,e) {
                    fData.append(e.name, e.value);
                });

                $('.ui-el-sortlist', form).each(function (i,e) {
                    var r = '';
                    $('>*', $(e)).each(function(i,e) {
                        r += '|' + e.id;
                    });
                    fData.append(e.id, r);
                });

                $('input[type=file]').each(function (i,e) {
                    for (var x=0;x<e.files.length;x++) {
                        fData.append(e.name, e.files[x], e.files[x].name);
                    };
                });

                Genesis.query(url, fData);
            }
            return false;
        },

        submitOnEnter: function (id) {
            $('#'+id+' input').keydown(function(e) {
                if (e.keyCode == 13) {
                    Genesis.submit(id, 'OK', null, false);
                }
            });
        },

        init: function () {
            Genesis.query('/handle/nothing');
            Genesis.Core.requestProgress();
        },

        checkUnload: function () {
            if (isProcessing)
                return "Genesis is currently processing an operation, if you leave this page you may lose unsaved data.";
        },

        appListClick: function (id) {
            $('#'+id).toggleClass('selected');
            $('#'+id).children('input').prop("checked", !($('#'+id).children('input').prop("checked")))
        },

        selectAllApps: function () {
            $('.ui-firstrun-appselect').addClass('selected');
            $('.ui-firstrun-appselect').children('input').prop("checked", true)
        },

        clearAppSelection: function () {
            $('.ui-firstrun-appselect').removeClass('selected');
            $('.ui-firstrun-appselect').children('input').prop("checked", false)
        },

        Core: {
            processResponse: function (data) {
                $('.modal').each( function (i, e) {
                    Genesis.UI.hideModal(e.id);
                });

                //Genesis.cancelWarning();

                // $('.ui-tooltip').tooltip('hide');

                $('#content').empty();
                $('#content').html(data);
                $('#content script').each(function (i,e) {
                    try {
                        eval($(e).text);
                    } catch (err) { }
                    $(e).text('');
                });
                $('.ui-tooltip').tooltip();
                if (timedAlerts && timedAlerts > 0) {
                    setTimeout(function () {$('.alert').alert('close')}, timedAlerts * 1000);
                };
                Genesis.UI.showLoader(false);
            },

            processOffline: function (data) {
                window.location.href = '/';
                Genesis.UI.showLoader(false);
            },

            requestProgress: function () {
                $.ajax({
                    url: '/core/progress',
                    success: function (j) {
                        j = JSON.parse(j);
                        for (var prg in j) {
                            if (j[prg].type === 'statusbox') {
                                Genesis.UI.setLoaderText(j[prg]);
                            } else {
                                $('#message-box').empty();
                                Genesis.Core.addProgress(j[prg]);
                            }
                        }
                    },
                    complete: function () {
                        setTimeout('Genesis.Core.requestProgress()', 2000);
                    }
                });
            },

            addProgress: function (desc) {
                var html;
                if (desc.can_abort) {
                    html = '<div class="alert alert-info alert-dismissable fade in"><a class="close" data-dismiss="alert" onclick="return Genesis.showWarning(\'';
                    html += 'Cancel background task for ' + desc.owner + '?\', \'aborttask/' + desc.id + '\');">&#215;</a>';
                } else {
                    html = '<div class="progress-box">';
                }
                html += '<i class="gen-info" style="line-height:1;"></i> <p><strong>' + desc.owner + '</strong> ' + desc.status + '</p></div>';
                $('#message-box').append(html);
            },
        },

        selectCategory: function (id) {
            $('.ui-el-category').removeClass('selected');
            $('.ui-el-top-category').removeClass('selected');
            $('#'+id).addClass('selected');
            Genesis.query('/handle/category/click/' + id);
            $(window).scrollTop(0);
            return false;
        },

        showWarning: function (text, btnid, cls, fid, action) {
            $('.modal-backdrop').stop()
            warning_button_id = btnid;
            if (typeof cls === "undefined") {
                warning_class = 'button';
            } else {
                warning_class = cls;
            }
            $('.warning-button').click({'fid': fid, 'action': action}, 
                Genesis.acceptWarning);
            $('#warning-text').html(text);
            $('html').append('<div id="shadeback" style="display:none;opacity:0"></div>');
            $('#shadeback').stop().fadeTo(250, 0.8, function () { $(this).show(); });
            $(window).scrollTop(0);
            $('#warningbox').center().fadeTo(250, 1, function () { $(this).show(); });
            return false;
        },

        cancelWarning: function () {
            $('.warning-button').unbind('click');
            $('#warningbox').fadeTo(250, 0, function () { $(this).hide(); });
            $('#shadeback').fadeTo(250, 0, function () { $(this).remove(); });
            return false;
        },

        acceptWarning: function (event) {
            Genesis.cancelWarning();
            if (event.data.fid) {
                Genesis.submit(event.data.fid, event.data.action);
            } else {
                Genesis.query('/handle/'+ warning_class +'/click/' + warning_button_id);
            }
            return false;
        },

        showAuthorization: function () {
            $('html').append('<div id="shadeback" style="display:none;opacity:0"></div>');
            $('#shadeback').stop().fadeTo(250, 0.8, function () { $(this).show(); });
            $('#authbox').center().fadeTo(250, 1, function () { $(this).show(); });
            $('#auth-string').focus();
            return false;
        },

        cancelAuthorization: function () {
            $('#authbox').fadeTo(250, 0);
            $('#shadeback').fadeTo(250, 0, function () { $(this).remove(); });
            return false;
        },

        addAlert: function (cls, msg, ico) {
            $('#message-box').append('<div class="alert alert-'+cls+' alert-dismissable fade in"><button type="button" class="close" data-dismiss="alert" aria-hidden="true">&#215;</button><i class="'+ico+'" style="line-height:1;"></i> '+msg+'</div>');
        },

        submitBugReport: function (rptid) {
            var rpt = $(rptid).val();
            $.ajax({
                type: "POST",
                url: "/error",
                data: JSON.stringify({"report": rpt, "comments": ""}),
                contentType: "application/json; charset=utf-8",
                dataType: "json",
                success: function (d) {
                    if (d.status == 200) {
                        Genesis.addAlert('success', 'Your error report was submitted successfully. Thank you!', 'gen-checkmark');
                        $('#reportbtn').addClass('disabled');
                    } else {
                        Genesis.addAlert('danger', 'Your error report was not submitted properly. Please open an issue manually.', 'gen-close');
                    };
                },
                failure: function (e) {Genesis.addAlert('danger', 'Your error report was not submitted properly. Please open an issue manually.', 'gen-close');}
            })
        },

        UI: {
            showAsModal: function (id) {
                $('#'+id).modal({backdrop: 'static', keyboard: false, show: true});
            },

            hideModal: function (id, remove) {
                $('#'+id).modal('hide');
                $('body').removeClass('modal-open');
                $('.modal-backdrop').fadeTo(250, 0, function () { $(this).remove(); });
            },

            showLoader: function (visible) {
                if (visible) {
                    $('#whiteout').show().fadeTo(200, 0.3);
                    $(window).scrollTop(0);
                    $('#pbox').show().center();
                    $('body').css('cursor', 'wait !important');
                    isProcessing = true;
                }
                else {
                    $('#whiteout').stop().fadeTo(250, 0, function () { $(this).hide(); });
                    $('#pbox').stop().hide();
                    $('#pbox-text').text('Please wait...');
                    $('body').css('cursor', '');
                    isProcessing = false;
                }
            },

            setLoaderText: function (desc) {
                if (desc.status) {
                    $('#pbox-text').text(desc.status);
                }
            },

            toggleTreeNode: function (id) {
                $('*[id=\''+id+'\']').toggle();
                Genesis.query('/handle/treecontainer/click/'+id, null, true);

                x = $('*[id=\''+id+'-btn\']');
                if (x.attr('src').indexOf('/dl/core/ui/tree-minus.png') < 0){
                    x.attr('src', '/dl/core/ui/tree-minus.png');
                } else {
                    x.attr('src', '/dl/core/ui/tree-plus.png');
                }
                return false;
            },

            editableActivate: function (id) {
                function applyActivation(id){
                    $('#'+id+'-normal').hide();
                    $('#'+id).fadeIn(600);
                }
                if(typeof id === 'string'){
                    applyActivation(id);
                } else { // Input is an array
                    for(var i = 0; i < id.length; i++){
                        applyActivation(id[i]);
                    }
                }
                return false;
            },
        }
    };
}());

window.onbeforeunload = Genesis.checkUnload;

jQuery.fn.center = function () {
    this.css("top", (
        Math.max(
            ($(window).height() - this.outerHeight()) / 2,
            0
        ) + $(window).scrollTop()
    ) + "px");

    this.css("left", Math.max(0,(($(window).width() - this.outerWidth()) / 2) + $(window).scrollLeft()) + "px");
    return this;
};


function noenter() {
    return !(window.event && window.event.keyCode == 13);
}

function ui_fill_custom_html(id, html) {
    document.getElementById(id).innerHTML = Base64.decode(html);
}

$(document).click(function (e) {
    $('.pop-trigger').each(function () {
        if ((!$(this).is(e.target) && $(this).has(e.target).length === 0 && $('.popover').has(e.target).length === 0)||($(e.target).is('.popover-link'))) {
            //$(this).popover('hide');
            if ($(this).data('bs.popover').tip().hasClass('in')) {
                $(this).popover('toggle');
            }
            
            return;
        }
    });
});
