"""
This file is part of OpenSesame.

OpenSesame is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

OpenSesame is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with OpenSesame.  If not, see <http://www.gnu.org/licenses/>.
"""

# Will be inherited by video_player
from libopensesame import item

# Will be inherited by qtvideo_player
from libqtopensesame import qtplugin

# Used to access the file pool
from libqtopensesame import pool_widget

# Used to throw exceptions
from libopensesame import exceptions

import libopensesame.generic_response

import os
import sys
import thread
import urlparse, urllib

# Gstreamer componentes
import gobject
import pygst
pygst.require("0.10")
import gst

# Rendering components
import pygame
from OpenGL.GL import *
from OpenGL.GLU import *

class media_player(item.item, libopensesame.generic_response.generic_response):

	"""The media_player plug-in offers advanced video playback functionality in OpenSesame, using pyffmpeg"""

	def __init__(self, name, experiment, string = None):

		"""
		Constructor. Link to the video can already be specified but this is optional

		Arguments:
		name -- the name of the item
		experiment -- the opensesame experiment

		Keyword arguments:
		string -- a definition string for the item (Default = None)
		"""

		# The version of the plug-in
		self.version = 1.0

		gobject.threads_init()
		self.gst_loop = gobject.MainLoop()
		
		self.paused = False
		self.item_type = "media_player"
		self.description = "Plays a video from file"
		self.duration = "keypress"
		self.fullscreen = "yes"
		self.playaudio = "yes"
		self.video_src = ""
		self.sendInfoToEyelink = "yes"
		self.event_handler = ""
		self.frameNo = 0
		self.event_handler_trigger = "on keypress"

		# The parent handles the rest of the construction
		item.item.__init__(self, name, experiment, string)

		# Indicate function for clean up that is run after the experiment finishes
		self.experiment.cleanup_functions.append(self.closeStreams)
	
	
	def calcScaledRes(self, screen_res, image_res):
		"""Calculate image size so it fits the screen
		Args
			screen_res (tuple)   -  Display window size/Resolution
			image_res (tuple)    -  Image width and height
	
		Returns
			tuple - width and height of image scaled to window/screen
		"""
		rs = screen_res[0]/float(screen_res[1])
		ri = image_res[0]/float(image_res[1])
	
		if rs > ri:
			return (int(image_res[0] * screen_res[1]/image_res[1]), screen_res[1])
		else:
			return (screen_res[0], int(image_res[1]*screen_res[0]/image_res[0]))

	def prepare(self):

		"""
		Opens the video file for playback and compiles the event handler code

		Returns:
		True on success, False on failure
		"""

		# Pass the word on to the parent
		item.item.prepare(self)

		# Give a sensible error message if the proper back-end has not been selected
		if not self.has("canvas_backend") or self.get("canvas_backend") != "legacy":
			raise exceptions.runtime_error("The media_player plug-in requires the legacy back-end. Sorry!")

		# Byte-compile the event handling code (if any)
		if self.event_handler.strip() != "":
			self._event_handler = compile(self.event_handler, "<string>", "exec")
		else:
			self._event_handler = None

		# Determine when the event handler should be called
		if self.event_handler_trigger == "on keypress":
			self._event_handler_always = False
		else:
			self._event_handler_always = True

		# Find the full path to the video file. This will point to some
		# temporary folder where the file pool has been placed
		path = self.experiment.get_file(str(self.eval_text(self.get("video_src"))))
		
		# Open the video file
		if not os.path.exists(path) or str(self.eval_text("video_src")).strip() == "":
			raise exceptions.runtime_error("Video file '%s' was not found in video_player '%s' (or no video file was specified)." % (os.path.basename(path), self.name))
		
		if self.experiment.debug:
			print "media_player.prepare(): loading '%s'" % path
		
		# Determine URI to file source
		path = os.path.abspath(path)
		path = urlparse.urljoin('file:', urllib.pathname2url(path))
		
		self.load(path)

		# Report success
		return True

	def load(self, vfile):
		"""
		Loads a videofile and makes it ready for playback

		Arguments:
		file -- the path tp the file to be played
		"""
		# Info required for color space conversion (YUV->RGB)
		self.caps = gst.Caps("video/x-raw-rgb")
		#self.caps = gst.Caps("video/x-raw-rgb, width=1920, height=1080")

		# Create videoplayer and load URI
		self.player = gst.element_factory_make("playbin2", "player")		
		self.player.set_property("uri", vfile)
		
		# Enable deinterlacing of video if necessary
		self.player.props.flags |= (1 << 9)		
		
		# Reroute frame output to Python
		self._videosink = gst.element_factory_make('appsink', 'videosink')		
		self._videosink.set_property('caps', self.caps)
		self._videosink.set_property('async', True)
		self._videosink.set_property('drop', True)
		self._videosink.set_property('emit-signals', True)
		self._videosink.connect('new-buffer', self.__handle_videoframe)		
		self.player.set_property('video-sink', self._videosink)

		# Set functions for handling player messages
		bus = self.player.get_bus()		
		bus.enable_sync_message_emission()
		bus.add_signal_watch()
		bus.connect("message", self.__on_message)
		
		# Preroll movie to get dimension data
		self.player.set_state(gst.STATE_PAUSED)
		
		# If movie is loaded correctly, info about the clip should be available
		if self.player.get_state(gst.CLOCK_TIME_NONE)[0] == gst.STATE_CHANGE_SUCCESS:
			pads = self._videosink.pads()			
			for pad in pads:			
				caps = pad.get_negotiated_caps()[0]
				self.vidsize = caps['width'], caps['height']
		else:
			raise exceptions.runtime_error("Failed to retrieve video size")
	
		if self.playaudio == "no":
			self.player.set_property("mute",True)				
			
		self.screen = self.experiment.surface
		self.file_loaded = True
		
		if self.fullscreen == "yes":
			self.destsize = self.calcScaledRes((self.experiment.width,self.experiment.height), self.vidsize)	
			print self.destsize
		else:
			self.destsize = self.vidsize
		self.vidPos = ((self.experiment.width - self.destsize[0]) / 2, (self.experiment.height - self.destsize[1]) / 2)		
			

	def __handle_videoframe(self, appsink):
		"""
		Callback method for handling a video frame

		Arguments:
		appsink -- the sink to which gst supplies the frame (not used)
		"""		
		buffer = self._videosink.emit('pull-buffer')		

		img = pygame.image.frombuffer(buffer.data, self.vidsize, "RGB")
		
		# Upscale image to new surfuace if presented fullscreen
		# Create the surface if it doesn't exist yet
		if self.fullscreen == "yes":		
			if not hasattr(self,"destSurf"):				
				self.destSurf = pygame.transform.scale(img, self.destsize)
			else:
				pygame.transform.scale(img, self.destsize, self.destSurf)
			self.screen.blit(self.destSurf, self.vidPos)
		else:
			self.screen.blit(img, self.vidPos)

		pygame.display.flip()
		
		self.frameNo += 1
		
	def __on_message(self, bus, message):
		t = message.type		
		if t == gst.MESSAGE_EOS:
			self.player.set_state(gst.STATE_NULL)	
			self.gst_loop.quit()
		elif t == gst.MESSAGE_ERROR:
			self.player.set_state(gst.STATE_NULL)
			err, debug = message.parse_error()
			self.gst_loop.quit()
			raise exceptions.runtime_error("Gst Error: %s" % err, debug)			

	def pause(self):

		"""Pauses playback"""

		self.paused = True
		self.player.set_state(gst.STATE_PAUSED)

	def unpause(self):

		"""Continues playback"""

		self.paused = False
		self.player.set_state(gst.STATE_PLAYING)

	def handleEvent(self, event = None):

		"""
		Allows the user to insert custom code. Code is stored in the event_handler variable.

		Arguments:
		event -- a dummy argument passed by the signal handler
		"""
		continue_playback = True

		try:
			exec(self._event_handler)
		except Exception as e:
			raise exceptions.runtime_error("Error while executing event handling code: %s" % e)

		if type(continue_playback) != bool:
			continue_playback = False

		return continue_playback

	
	def run(self):

		"""
		Starts the playback of the video file. You can specify an optional callable object to handle events between frames (like keypresses)
		This function needs to return a boolean, because it determines if playback is continued or stopped. If no callable object is provided
		playback will stop when the ESC key is pressed

		Returns:
		True on success, False on failure
		"""
		print "Starting video playback"
                
		# Log the onset time of the item
		self.set_item_onset()

		# Set some response variables, in case a response will be given
		if self.experiment.start_response_interval == None:
			self.experiment.start_response_interval = self.get("time_%s" % self.name)
			self.experiment.end_response_interval = self.experiment.start_response_interval
		self.experiment.response = None

		if self.file_loaded:	
			self.screen.fill((0,0,0))
			# Start gst loop (which listens for events from the player)
			thread.start_new_thread(self.gst_loop.run, ())						
			
			# Wait for gst loop to start running, but do so for a max of 50ms		
			counter = 0
			while not self.gst_loop.is_running(): 		
				pygame.time.wait(5)
				counter += 1
				if counter > 10:
					print >> sys.stderr, "ERROR: gst loop failed to start"
					sys.exit(1)
			
			# Signal player to start video playback
			self.player.set_state(gst.STATE_PLAYING)			
						
			self.playing = True
			startTime = pygame.time.get_ticks()
			while self.playing:
				if self._event_handler_always:
					self.playing = self.handleEvent()
				else:
					# Process all events
					for event in pygame.event.get():
						if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
							if self._event_handler != None:
								self.playing = self.handleEvent(event)
							elif event.type == pygame.KEYDOWN and self.duration == "keypress":
								self.playing = False
								self.experiment.response = pygame.key.name(event.key)
								self.experiment.end_response_interval = pygame.time.get_ticks()
							elif event.type == pygame.MOUSEBUTTONDOWN and self.duration == "mouseclick":
								self.playing = False
								self.experiment.response = event.button
								self.experiment.end_response_interval = pygame.time.get_ticks()

							# Catch escape presses
							if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
								raise exceptions.runtime_error("The escape key was pressed")

				# Advance to the next frame if the player isn't paused
				if not self.paused:					
					if self.sendInfoToEyelink == "yes" and hasattr(self.experiment,"eyelink") and self.experiment.eyelink.connected():
						frame_no = self.frameNo
						self.experiment.eyelink.log("videoframe %s" % frame_no)
						self.experiment.eyelink.status_msg("videoframe %s" % frame_no )

					# Check if max duration has been set, and exit if exceeded
					if type(self.duration) == int:
						if pygame.time.get_ticks() - startTime > (self.duration*1000):
							self.playing = False

				if not self.gst_loop.is_running():
					self.playing = False
				elif not self.playing and self.gst_loop.is_running():
					self.player.set_state(gst.STATE_NULL)
					self.gst_loop.quit()

			libopensesame.generic_response.generic_response.response_bookkeeping(self)			
			return True

		else:
			raise exceptions.runtime_error("No video loaded")
			return False

	def closeStreams(self):
	
		"""
		A cleanup function, to make sure that the video files are closed

		Returns:
		True on success, False on failure
		"""
		if self.gst_loop.is_running():
			self.player.set_state(gst.STATE_NULL)
			self.gst_loop.quit()
		

	def var_info(self):

		return libopensesame.generic_response.generic_response.var_info(self)		

class qtmedia_player(media_player, qtplugin.qtplugin):

	"""Handles the GUI aspects of the plug-in"""

	def __init__(self, name, experiment, string = None):

		"""
		Constructor. This function doesn't do anything specific
		to this plugin. It simply calls its parents. Don't need to
		change, only make sure that the parent name matches the name
		of the actual parent.

		Arguments:
		name -- the name of the item
		experiment -- the opensesame experiment

		Keyword arguments:
		string -- a definition string for the item (Default = None)
		"""

		# Pass the word on to the parents
		media_player.__init__(self, name, experiment, string)
		qtplugin.qtplugin.__init__(self, __file__)

	def init_edit_widget(self):

		"""This function creates the controls for the edit widget"""

		# Lock the widget until we're doing creating it
		self.lock = True

		# Pass the word on to the parent
		qtplugin.qtplugin.init_edit_widget(self, False)

		# We don't need to bother directly with Qt4, since the qtplugin class contains
		# a number of functions which directly create controls, which are automatically
		# applied etc. A list of functions can be found here:
		# http://files.cogsci.nl/software/opensesame/doc/libqtopensesame/libqtopensesame.qtplugin.html
		self.add_filepool_control("video_src", "Video file", self.browse_video, default = "", tooltip = "A video file")
		self.add_combobox_control("fullscreen", "Resize to fit screen", ["yes", "no"], tooltip = "Resize the video to fit the full screen")
		self.add_combobox_control("playaudio", "Play audio", ["yes", "no"], tooltip = "Specifies if the video has to be played with audio, or in silence")
		self.add_combobox_control("sendInfoToEyelink", "Send frame no. to EyeLink", ["yes", "no"], tooltip = "If an eyelink is connected, then it will receive the number of each displayed frame as a msg event.\r\nYou can also see this information in the eyelink's status message box.\r\nThis option requires the installation of the OpenSesame EyeLink plugin and an established connection to the EyeLink.")
		self.add_combobox_control("event_handler_trigger", "Call custom Python code", ["on keypress", "after every frame"], tooltip = "Determine when the custom event handling code is called.")
		self.add_line_edit_control("duration", "Duration", tooltip = "Expecting a value in seconds, 'keypress' or 'mouseclick'")
		self.add_editor_control("event_handler", "Custom Python code for handling keypress and mouseclick events (See Help for more information)", syntax = True, tooltip = "Specify how you would like to handle events like mouse clicks or keypresses. When set, this overrides the Duration attribute")
		self.add_text("<small><b>Media Player OpenSesame Plugin v%.2f, Copyright (2011) Daniel Schreij</b></small>" % self.version)

		# Unlock
		self.lock = True

	def browse_video(self):

		"""
		This function is called when the browse button is clicked
		to select a video from the file pool. It displays a filepool
		dialog and changes the video_src field based on the selection.
		"""

		s = pool_widget.select_from_pool(self.experiment.main_window)
		if str(s) == "":
				return
		self.auto_line_edit["video_src"].setText(s)
		self.apply_edit_changes()

	def apply_edit_changes(self):

		"""
		Set the variables based on the controls. The code below causes
		this to be handles automatically. Don't need to change.

		Returns:
		True on success, False on failure
		"""

		# Abort if the parent reports failure of if the controls are locked
		if not qtplugin.qtplugin.apply_edit_changes(self, False) or self.lock:
			return False

		# Refresh the main window, so that changes become visible everywhere
		self.experiment.main_window.refresh(self.name)

		# Report success
		return True

	def edit_widget(self):

		"""
		Set the controls based on the variables. The code below causes
		this to be handled automatically. Don't need to change.
		"""

		# Lock the controls, otherwise a recursive loop might arise
		# in which updating the controls causes the variables to be
		# updated, which causes the controls to be updated, etc...
		self.lock = True

		# Let the parent handle everything
		qtplugin.qtplugin.edit_widget(self)

		# Unlock
		self.lock = False

		# Return the _edit_widget
		return self._edit_widget

