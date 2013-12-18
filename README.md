# GStreamer based Media Player plugin

Copyright 2010-2014 Daniel Schreij (<d.schreij@vu.nl>)

The media_player_gst plug-in adds video playback capabilities to the [OpenSesame experiment builder][opensesame]. This plug-in uses the [GStreamer framework][gst] as its basis. It can handle most modern video and audio formats, as long as they are supported by the [libav library][libav]. This plugin has some benefits compared to the other media player plugins that are currently available for OpenSesame, such as:

- Works in all backends (whereas media_player_vlc was only limited to the legacy or expyriment backends)
- Frames are drawn internally by OpenSesame, offering more control such as determining which frame is currently shown, making screenshots, or even the possibility of real-time drawing on top of the shown video frames.
- Multi-platform; should work in Windows, Linux and (in the future) Mac and Android versions of OpenSesame.
- This framework is the way to go for playing media in my opinion and I (hope to) keep actively developing it in the future (and as always, any help with this is much appreciated).

##Plug-in installation
If this plugin came with your OpenSesame installation, it should work directly out of the box. If it did not (for instance because you are running OpenSesame from source), you will probably need to install the GStreamer framework yourself before you can use the plugin. 

### Ubuntu 

In (Ubuntu) Linux, you can easily install GStreamer with the command

    sudo apt-get install gstreamer0.10-tools gstreamer-tools gstreamer0.10-plugins-base gstreamer0.10-ffmpeg 

(if it is not already installed by default, which is sometimes the case in Ubuntu)

### Windows

For Windows (and also for Linux if the above did not work for you or you are using another distribution than Ubuntu) you can download the appropriate GStreamer distributables from [the GStreamer website][gst-dl]. You only need to install the runtime files (thus you can omit the development files even though the website states you need to install both). Whether you need to download the 32-bit or 64-bit variant depends on your Python installation. If you have installed a 32-bit Python, you will need the 32-bit version of GStreamer and vice versa for 64-bit (Note that this has nothing to do with the architecture of your OS: if you installed a 32-bit Python on your 64-bit OS, you still require the 32-bit version of GStreamer). 

Under Windows select custom installation and make sure the box before `GStreamer libav wrapper` is checked. This add-on contains the codecs you need to be able to play most current video and audio formats and if you forget this, you will inevitably bump into problems sooner or later, so don't ;). To save disk space you can deselect all options beginning with GTK (but can also leave these options on).

### OS X

On OS X you can also install GStreamer by using the installer from [the GStreamer SDK website][gst-dl]. Don't forget to install the libav wrapper plugin! You can do this by clicking on *Customize* in the "Installation Type" section and then tick the box next to *GStreamer libav wrapper*. You only need to install the runtime files (and not the development files even though this is stated as necessary on the website).

### Running the plugin

Extract the the plugin as a folder named media_player_gst in the OpenSesame/plugin folder (or ./opensesame/plugins on Linux/OS X or AppData/Roaming/opensesame/plugins on Windows).
The plugin will automatically find your GStreamer installation if it has been installed to its default location (which on windows is usually `c:\gstreamer-sdk\`). If you needed to install it to a different folder, you will need to edit the variable GSTREAMER_PATH somewhere at the top section of media_player_gst.py and make it point to the location at which you have installed GStreamer.

If you followed all the above steps correctly, OpenSesame should now be able to succesfully import the media_player_gst plugin, when it is placed in your experiment structure, and be able to play any movies it is supplied.

## Plugin settings
The plugin offers the following configuration options from the GUI:

- *Video file* - the video file to be played. This field allows variables such as [video_file], of which you can specify the value in loop items
- *Play audio* - specifies whether the video is to be played with audio on or in silence (muted)
- *Fit video to screen* - specifies whether the video should be played in its original size, or if it should be scaled to fit the size of the window/screen. The rescaling procedure maintains the original aspect ratio of the movie.
- *Loop playback* - specifies if the video should be looped, meaning that it will start again from the beginning once the end of of the movie is reached.
- *Send frame no. to EyeLink* - if this computer is connected to an SR Research Eyelink eye tracking device, this specifies if a message should be sent once a new frame is displayed. This enables you to time-lock gaze information to frame display times (i.e. determine what the observer looked at during a frame)
- *Duration* - Specifies how long the movie should be displayed. Expects a value in seconds, 'keypress' or 'mouseclick'. It it has one of the last values, playback will stop when a key is pressed or the mouse button is clicked.

## Custom Python code for handling keypress and mouseclick events
This plugin also offers functionality to execute custom event handling code after each frame, or after a key press or mouse click (Note that execution of code after each frame nullifies the 'keypress' option in the duration field; Escape presses however are still listened to). This is for instance useful, if one wants to count how many times a participants presses space (or any other button) during the showtime of the movie.

There are a couple of variables accessible in the script you enter here:
- `continue_playback` (True or False) - Determines if the movie should keep on playing. This variable is set to True by default while the movie is playing. If you want to stop playback from your script, simply set this variable to False and playback will stop.
- `exp` - A convenience variable pointing to the self.experiment object
- `frame` - The number of the current frame that is being displayed
- `mov_width` - The width of the movie in px
- `mov_height` - The height of the movie in px
- `paused` - *True* when playback is currently paused, *False* if movie is currently running
- `event` - This variable is somewhat special, as its contents depend on whether a key or mouse button was pressed during the last frame. If this is not the case, the event variable will simply point to *None*. If a key was pressed, event will contain a tuple with at the first position the value "key" and at the second position the value of the key that was pressed, for instance ("key","space"). If a mouse button was clicked, the event variable will contain a tuple with at the first position the value "mouse" and at the second position the number of the mouse button that was clicked, for instance ("mouse", 2). In the rare occasion that multiple buttons or keys were pressed at the same time during a frame, the event variable will contain a list of these events, for instance [("key","space"),("key", "x"),("mouse",2)]. In this case, you will need to traverse this list in your code and pull out all events relevant to you.

Next to these variables you also have the following functions at your disposal:

- `pause()` - Pauses playback when the movie is running, and unpauses it otherwise (you could regard it as a pause/unpause toggle)

[opensesame]: http://www.cogsci.nl/opensesame
[gst]: http://www.gstreamer.com/
[gst-dl]: http://docs.gstreamer.com/display/GstSDK/Installing+the+SDK
[libav]: http://libav.org/
