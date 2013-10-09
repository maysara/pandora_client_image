#!/usr/bin/python
# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4
# GPL 2010
from __future__ import division, with_statement

import fractions
from glob import glob
import json
import os
import re
import sqlite3
import subprocess
import sys
import shutil
import tempfile
import time

import ox

from utils import avinfo, AspectRatio, run_command


def command(program):
    local = os.path.expanduser('~/.ox/bin/%s' % program)
    if os.path.exists(local):
        program = local
    return program

def frame(video, target, position):
    fdir = os.path.dirname(target)
    if fdir and not os.path.exists(fdir):
        os.makedirs(fdir)

    '''
    #oxframe
    cmd = ['oxframe', '-i', video, '-p', str(position), '-o', target]
    print cmd
    r = run_command(cmd)
    return r == 0
    '''

    '''
    #mplayer
    cwd = os.getcwd()
    target = os.path.abspath(target)
    framedir = tempfile.mkdtemp()
    os.chdir(framedir)
    cmd = ['mplayer', '-noautosub', video, '-ss', str(position), '-frames', '2', '-vo', 'png:z=9', '-ao', 'null']
    print cmd
    r = run_command(cmd)
    images = glob('%s/*.png' % framedir)
    if images:
        shutil.move(images[-1], target)
        r = 0
    else:
        r = 1
    os.chdir(cwd)
    shutil.rmtree(framedir)
    return r == 0
    '''
    #ffmpeg
    pre = position - 2
    if pre < 0:
        pre = 0
    else:
        position = 2
    cmd = [command('ffmpeg'), '-y', '-ss', str(pre), '-i', video, '-ss', str(position),
            '-vf', 'scale=iw*sar:ih',
            '-an', '-vframes', '1', target]
    r = run_command(cmd)
    return r == 0

def supported_formats():
    p = subprocess.Popen([command('ffmpeg'), '-codecs'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    return {
        #'ogg': 'libtheora' in stdout and 'libvorbis' in stdout,
        'webm': 'libvpx' in stdout and 'libvorbis' in stdout,
        'mp4': 'libx264' in stdout and 'libvo_aacenc' in stdout,
    }

def video_cmd(video, target, profile, info):

    if not os.path.exists(target):
        ox.makedirs(os.path.dirname(target))

    '''
        look into
            lag
            mb_static_threshold
            qmax/qmin
            rc_buf_aggressivity=0.95
            token_partitions=4
            level / speedlevel
            bt?
    '''
    profile, format = profile.split('.')
    bpp = 0.17

    if profile == '1080p':
        height = 1080

        audiorate = 48000
        audioquality = 6
        audiobitrate = None
        audiochannels = None

    if profile == '720p':
        height = 720

        audiorate = 48000
        audioquality = 5
        audiobitrate = None
        audiochannels = None
    if profile == '480p':
        height = 480

        audiorate = 44100
        audioquality = 3
        audiobitrate = None
        audiochannels = 2
    elif profile == '432p':
        height = 432
        audiorate = 44100
        audioquality = 2
        audiobitrate = None
        audiochannels = 2
    elif profile == '360p':
        height = 360

        audiorate = 44100
        audioquality = 1
        audiobitrate = None
        audiochannels = 1
    elif profile == '288p':
        height = 288

        audiorate = 44100
        audioquality = 0
        audiobitrate = None
        audiochannels = 1
    elif profile == '240p':
        height = 240

        audiorate = 44100
        audioquality = 0
        audiobitrate = None
        audiochannels = 1
    elif profile == '144p':
        height = 144

        audiorate = 22050
        audioquality = -1
        audiobitrate = '22k'
        audiochannels = 1
    else:
        height = 96

        audiorate = 22050
        audioquality = -1
        audiobitrate = '22k'
        audiochannels = 1

    if info['video'] and 'display_aspect_ratio' in info['video'][0]:
        dar = AspectRatio(info['video'][0]['display_aspect_ratio'])
        fps = AspectRatio(info['video'][0]['framerate'])
        width = int(dar * height)
        width += width % 2 
        extra = []
        if fps == 50:
            fps = 25
            extra += ['-r', '25']
        if fps == 60:
            fps = 30
            extra += ['-r', '30']
        fps = min(float(fps), 30)
        bitrate = height*width*fps*bpp/1000
        aspect = dar.ratio
        #use 1:1 pixel aspect ratio if dar is close to that
        if abs(width/height - dar) < 0.02:
            aspect = '%s:%s' % (width, height)

        video_settings = [
            '-vb', '%dk'%bitrate,
            '-aspect', aspect,
            '-g', '%d' % int(fps*5),
            '-vf', 'yadif,hqdn3d,scale=%s:%s'%(width, height),
        ] + extra
        if format == 'webm':
            video_settings += [
                '-deadline', 'good',
                '-cpu-used', '0',
                '-lag-in-frames', '16',
                '-auto-alt-ref', '1',
            ]
        if format == 'mp4':
            #quicktime does not support bpyramid
            '''
            video_settings += [
                '-vcodec', 'libx264',
                '-flags', '+loop+mv4',
                '-cmp', '256',
                '-partitions', '+parti4x4+parti8x8+partp4x4+partp8x8+partb8x8',
                '-me_method', 'hex',
                '-subq', '7',
                '-trellis', '1',
                '-refs', '5',
                '-bf', '3',
                '-flags2', '+bpyramid+wpred+mixed_refs+dct8x8',
                '-coder', '1',
                '-me_range', '16',
                '-keyint_min', '25', #FIXME: should this be related to fps?
                '-sc_threshold','40',
                '-i_qfactor', '0.71',
                '-qmin', '10', '-qmax', '51',
                '-qdiff', '4'
            ]
            '''
            video_settings += [
                '-vcodec', 'libx264',
                '-flags', '+loop+mv4',
                '-cmp', '256',
                '-partitions', '+parti4x4+parti8x8+partp4x4+partp8x8+partb8x8',
                '-me_method', 'hex',
                '-subq', '7',
                '-trellis', '1',
                '-refs', '5',
                '-bf', '0',
                '-flags2', '+mixed_refs',
                '-coder', '0',
                '-me_range', '16',
                '-sc_threshold', '40',
                '-i_qfactor', '0.71',
                '-qmin', '10', '-qmax', '51',
                '-qdiff', '4'
            ]
        video_settings += ['-map', '0:%s,0:0'%info['video'][0]['id']]
    else:
        video_settings = ['-vn']

    if info['audio']:
        if video_settings == ['-vn'] or not info['video']:
            n = 0
        else:
            n = 1
        video_settings += ['-map', '0:%s,0:%s' % (info['audio'][0]['id'], n)]
        audio_settings = ['-ar', str(audiorate), '-aq', str(audioquality)]
        ac = info['audio'][0].get('channels', audiochannels)
        if ac:
            ac = min(ac, audiochannels)
        else:
            ac = audiochannels
        audio_settings += ['-ac', str(ac)]
        if audiobitrate:
            audio_settings += ['-ab', audiobitrate]
        if format == 'mp4':
            audio_settings += ['-acodec', 'libvo_aacenc']
        else:
            audio_settings += ['-acodec', 'libvorbis']
    else:
        audio_settings = ['-an']

    cmd = [command('ffmpeg'), '-y', '-i', video, '-threads', '4'] \
          + audio_settings \
          + video_settings

    if format == 'webm':
        cmd += ['-f', 'webm', target]
    elif format == 'mp4':
        #mp4 needs postprocessing(qt-faststart), write to temp file
        cmd += ["%s.mp4" % target]
    else:
        cmd += [target]
    return cmd

def video(video, target, profile, info):
    cmd = video_cmd(video, target, profile, info)
    profile, format = profile.split('.')
    #r = run_command(cmd, -1)
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        p.wait()
        r = p.returncode
        if format == 'mp4':
            cmd = [command('qt-faststart'), "%s.mp4" % target, target]
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                      stdout=open('/dev/null', 'w'),
                                      stderr=subprocess.STDOUT)
            p.communicate()
            os.unlink("%s.mp4" % target)
        print 'Input:\t', video
        print 'Output:\t', target
    except KeyboardInterrupt:
        p.kill()
        r = 1
        if os.path.exists(target):
            print "\n\ncleanup unfinished encoding:\nremoving", target
            print "\n"
            os.unlink(target)
        if format == 'mp4' and os.path.exists("%s.mp4" % target):
            os.unlink("%s.mp4" % target)
        sys.exit(1)
    return r == 0
