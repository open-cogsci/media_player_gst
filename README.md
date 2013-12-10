# GStreamer based Media Player 

Copyright 2010-2014 Daniel Schreij <d.schreij@vu.nl>

The media_player_gst plug-in adds video playback capabilities to the [OpenSesame experiment builder][opensesame]. This plug-in uses the [GStreamer framework][gst] as its basis. It can handle most modern video and audio formats, as long as they are supported by the [libav library][libav].

##Plug-in installation
If this plugin did not come together with your OpenSesame installation, you will probably need to install the GStreamer framework yourself. Otherwise it should just work fine out of the box. In (Ubuntu) Linux, you can easily install GStreamer with the command

    sudo apt-get install gstreamer0.10-tools gstreamer-tools gstreamer0.10-plugins-base gstreamer0.10-ffmpeg 

(if it is not installed already, as is sometimes the case by default in Ubuntu)

For Windows and Mac (and also for Linux if the above did not work for you) you can download the appropriate GStreamer distributables from [the GStreamer website][gst-dl]. Whether you need to download the 32-bit or 64-bit variant depends on your Python installation. If you have installed a 32-bit Python, you will need the 32-bit version of GStreamer and vice versa for 64-bit (Note that this has nothing to do with the architecture of your OS: if you installed a 32-bit Python on your 64-bit OS, you still require the 32-bit version of GStreamer). 

Under Windows select custom installation, and also check the box before `libav wrapper`. This add-on contains the codecs you need to be able to play most current video and audio formats and if you forget this, you will inevitably bump into problems sooner or later, so don't ;)

The plugin will automatically find your GStreamer installation if it has been installed to the default location (which on windows is `c:\gstreamer-sdk\`). If you needed to install it to a different folder, you will have to edit the variable GSTREAMER_PATH somewhere in the top of media_player_gst.py and make it point to the location at which you have installed GStreamer.


[opensesame]: http://www.cogsci.nl/opensesame
[gst]: http://www.gstreamer.com/
[gst-dl]: http://docs.gstreamer.com/display/GstSDK/Installing+the+SDK
[libav]: http://libav.org/

