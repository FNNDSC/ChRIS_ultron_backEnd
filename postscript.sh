#!/bin/bash
#
# Once a ChRIS/CUBE ecosystem has been fully instantiated from a run of the
# 'make.sh' script, the system will by default only have a few test/dummy
# plugins available. This is to keep instantiation times comparatively fast,
# especially in the case of development where the whole ecosystem is created
# and destroyed multiple times.
#
# In order to add more plugins to an instantiated system, this postscript.sh
# can be used to add plugins and also provide an easy cheat sheet for adding
# more.
#

./plugin_add.sh  "\
                    fnndsc/pl-dsdircopy,                            \
                    fnndsc/pl-simplefsapp^moc,                      \
                    fnndsc/pl-simpledsapp^moc,                      \
                    fnndsc/pl-s3push,                               \
                    fnndsc/pl-pfdicom_tagextract,                   \
                    fnndsc/pl-pfdicom_tagsub,                       \
                    fnndsc/pl-mpcs,                                 \
                    fnndsc/pl-mpcs^moc,                             \
                    fnndsc/pl-fshack,                               \
                    fnndsc/pl-fastsurfer_inference,                 \
                    fnndsc/pl-freesurfer_pp,                        \
                    fnndsc/pl-freesurfer_pp^moc,                    \
                    fnndsc/pl-z2labelmap,                           \
                    fnndsc/pl-z2labelmap^moc,                       \
                    fnndsc/pl-mri10yr06mo01da_normal,               \
                    fnndsc/pl-mri10yr06mo01da_normal^moc,           \
                    fnndsc/pl-mgz2lut_report,                       \
                    fnndsc/pl-pfdo_mgz2img,                         \
		    jonocameron/pl-sevstack,                        \
                    fnndsc/pl-topologicalcopy,                      \
                    fnndsc/pl-brainmgz,                             \
                    fnndsc/pl-pfdorun,                              \
                    fnndsc/pl-mgz2imageslices,                      \
                    fnndsc/pl-multipass,                            \
                    fnndsc/pl-heatmap
"

#
# Adding additional users
# Users can be added using some specific variation of the
# following:
#
# CUBE USERS
# For "superusers"
#####user_add.sh -U "rudolph:rudolph1234:rudolph.pienaar@gmail.com"
# For "normal users"
#####user_add.sh    "rpienaar:rudolph1234:rppienaar@gmail.com"
#
# STORE USERS
# For "superusers"
#####user_add.sh -U -S "rudolph:rudolph1234:rudolph.pienaar@gmail.com"
# For "normal users"
#####user_add.sh -S    "rpienaar:rudolph1234:rppienaar@gmail.com"
#

