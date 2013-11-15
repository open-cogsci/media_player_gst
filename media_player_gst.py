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

import os
if os.name == "nt":
	os.environ['PATH'] = 'C:/gstreamer-sdk/0.10/x86/bin' + ';' + os.environ['PATH']

import thread
import time
import urlparse, urllib



# Will be inherited by video_player
from libopensesame import item

# Will be inherited by qtvideo_player
from libqtopensesame import qtplugin

# Used to access the file pool
from libqtopensesame import pool_widget

# Used to throw exceptions
from libopensesame.exceptions import osexception

import libopensesame.generic_response

# Gstreamer componentes
import gobject
import pygst
pygst.require("0.10")
import gst

# Rendering components
import pygame
import pyglet
GL = pyglet.gl


class legacy_handler:
	def __init__(self, main_player, screen, custom_event_code = None):
		"""
		Constructor. Set variables to be used in rest of class.

		Arguments:
		main_player -- reference to the main_player_gst object (which should instantiate this class)
		screen -- reference to the pygame display surface		

		Keyword arguments:
		custom_event_code -- (Compiled) code that is to be called after every frame
		"""		
		
		self.main_player = main_player
		self.screen = screen
		self.custom_event_code = custom_event_code		

		if self.main_player.fullscreen == "yes":
			# Already create surfaces so this does not need to be redone for every frame
			# The time process a single frame should be much shorter this way.				
			self.img = pygame.Surface(self.main_player.vidsize, pygame.SWSURFACE, 24, (255, 65280, 16711680, 0))
			# Create pygame bufferproxy object for direct surface access
			# This saves us from using the time consuming pygame.image.fromstring() method as the frame will be
			# supplied in a format that can be written directly to the bufferproxy		
			self.imgBuffer = self.img.get_buffer()
			self.dest_surface = pygame.Surface	(self.main_player.destsize, pygame.SWSURFACE, 24, (255, 65280, 16711680, 0))		
		
	def handle_videoframe(self, frame):
		"""
		Callback method for handling a video frame

		Arguments:
		frame - the video frame supplied as a str/bytes object
		"""		

		self.screen.fill(pygame.Color(str(self.main_player.experiment.background)))
		if hasattr(self, "dest_surface"):
			self.imgBuffer.write(frame, 0)
			pygame.transform.scale(self.img, self.main_player.destsize, self.dest_surface)
			self.screen.blit(self.dest_surface, self.main_player.vidPos)
		else:			
			self.screen.blit(pygame.image.fromstring(frame, self.main_player.vidsize, "RGB"), self.main_player.vidPos)		
	
	def flip(self):
		pygame.display.flip()
		
	def draw_buffer(self):
		"""
		Dummy function as the frame is already drawn in handle_videoframe()
		"""
		pass
	
	def pump_events(self):
		pygame.event.pump()
	
	def process_user_input(self):
		# Process all events
		continue_playback = True
	
		for event in pygame.event.get():
			if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
				if self.custom_event_code != None:
					if event.type == pygame.KEYDOWN:
						continue_playback = self.process_user_input_customized(("key", pygame.key.name(event.key)))
					elif event.type == pygame.MOUSEBUTTONDOWN:
						continue_playback = self.process_user_input_customized(("mouse", event.button))						
				elif event.type == pygame.KEYDOWN and self.main_player.duration == "keypress":					
					self.main_player.experiment.response = pygame.key.name(event.key)
					self.main_player.experiment.end_response_interval = pygame.time.get_ticks()
					continue_playback = False
				elif event.type == pygame.MOUSEBUTTONDOWN and self.main_player.duration == "mouseclick":					
					self.main_player.experiment.response = event.button
					self.main_player.experiment.end_response_interval = pygame.time.get_ticks()
					continue_playback = False
		
				# Catch escape presses
				if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
					self.main_player.playing = False
					raise osexception("The escape key was pressed")
		
		return continue_playback
					
	def process_user_input_customized(self, event=None):

		"""
		Allows the user to insert custom code. Code is stored in the event_handler variable.

		Arguments:
		event -- a tuple containing the type of event (key or mouse button press)
			   and the value of the key or mouse button pressed (which character or mouse button)
		"""

		# Listen for escape presses and collect keyboard and mouse presses if no event has been passed to the function
		# If only one button press or mouse press is in the event que, the resulting event variable will just be a tuple
		# Otherwise the collected event tuples will be put in a list, which the user can iterate through with his custom code
		# This way the user will have either
		#  1. a single tuple with the data of the event (either collected here from the event que or passed from process_user_input)
		#  2. a list of tuples containing all key and mouse presses that have been pulled from the event queue		
		
		if event is None:
			events = pygame.event.get()
			event = []  # List to contain collected info on key and mouse presses			
			for ev in events:
				if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
					self.main_player.playing = False
					raise osexception("The escape key was pressed")								
				elif ev.type == pygame.KEYDOWN or ev.type == pygame.MOUSEBUTTONDOWN:
					# Exit on ESC press					
					if ev.type == pygame.KEYDOWN:
						event.append(("key", pygame.key.name(ev.key)))
					elif ev.type == pygame.MOUSEBUTTONDOWN:
						event.append(("mouse", ev.button))
			# If there is only one tuple in the list of collected events, take it out of the list 
			if len(event) == 1:
				event = event[0]
																
		continue_playback = True

		frame = self.main_player.frame_no
		scr_width = self.main_player.experiment.width
		scr_height = self.main_player.experiment.height
		
		#Ease callable pause function
		pause = self.main_player.pause
		unpause = self.main_player.unpause

		try:
			exec(self.custom_event_code)
		except Exception as e:
			self.main_player.playing = False
			raise osexception("Error while executing event handling code: %s" % e)

		if type(continue_playback) != bool:
			continue_playback = False

		return continue_playback
		
class psychopy_handler:
	def __init__(self, main_player, screen, custom_event_code = None):	
		self.main_player = main_player
		self.win = screen
		self.frame = None
				
	
	def handle_videoframe(self, frame):
		"""
		Callback method for handling a video frame

		Arguments:
		appsink -- the sink to which gst supplies the frame (not used)
		"""			
		
		# Create imageData object if not yet available. Otherwise just set the
		# data of the available object (progably faster?)
		if self.frame is None:		
			self.frame = pyglet.image.ImageData(self.main_player.vidsize[0], self.main_player.vidsize[1], "RGB", frame)
		else:
			self.frame.set_data("RGB", self.main_player.vidsize[0] * 3, frame)
			
		
	def draw_buffer(self):												
		if not hasattr(self,"dim"):		
			self.dim = self.main_player.calcScaledRes((2,2), (self.main_player.experiment.width, self.main_player.experiment.height), "float")
						
		GL.glLoadIdentity()		
		GL.glTranslatef(-1, -1 + self.dim[1]/2, 0)		
		GL.glColor4f(1,1,1,1)
					
		if self.frame:
			self.frame.blit(0,1,0, self.dim[0],-self.dim[1])
		
		self.win.flip()
		
	def flip(self):
		pass
		#self.win.flip(clearBuffer=False)
		
	def pump_events(self):
		pass
		
	def process_user_input(self):
		return True
		
	def process_user_input_customized(self, event=None):
		return True
	
	
class expyriment_handler:
	def __init__(self, main_player, screen):
		import OpenGL.GL as GL
		self.main_player = main_player
		self.screen = screen
	
	def handle_videoframe(self, appsink):
		"""
		Callback method for handling a video frame

		Arguments:
		appsink -- the sink to which gst supplies the frame (not used)
		"""	
		pass	
	
	def process_user_input(self):
		return True
		
	def process_user_input_customized(self, event=None):
		return True
	
	

class media_player_gst(item.item, libopensesame.generic_response.generic_response):

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
		self.frame_no = 0
		self.event_handler_trigger = "on keypress"

		# The parent handles the rest of the construction
		item.item.__init__(self, name, experiment, string)

		# Indicate function for clean up that is run after the experiment finishes
		self.experiment.cleanup_functions.append(self.close_streams)
	
	
	def calcScaledRes(self, screen_res, image_res, unit="int"):
		"""Calculate image size so it fits the screen
		Args
			screen_res (tuple)   -  Display window size/Resolution
			image_res (tuple)    -  Image width and height
	
		Returns
			tuple - width and height of image scaled to window/screen
		"""
		rs = screen_res[0]/float(screen_res[1])
		ri = image_res[0]/float(image_res[1])
	
		if unit == "int":
			if rs > ri:
				return (int(image_res[0] * screen_res[1]/image_res[1]), screen_res[1])
			else:
				return (screen_res[0], int(image_res[1]*screen_res[0]/image_res[0]))
		elif unit == "float":
			if rs > ri:
				return ((float(image_res[0]) * screen_res[1]/image_res[1]), screen_res[1])
			else:
				return (screen_res[0], (float(image_res[1])*screen_res[0]/image_res[0]))

	def prepare(self):

		"""
		Opens the video file for playback and compiles the event handler code

		Returns:
		True on success, False on failure
		"""

		# Pass the word on to the parent
		item.item.prepare(self)

		# Byte-compile the event handling code (if any)
		if self.event_handler.strip() != "":
			custom_event_handler = compile(self.event_handler, "<string>", "exec")
		else:
			custom_event_handler = None

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
			raise osexception("Video file '%s' was not found in video_player '%s' (or no video file was specified)." % (os.path.basename(path), self.name))
		
		if self.experiment.debug:
			print "media_player.prepare(): loading '%s'" % path
		
		# Determine URI to file source
		path = os.path.abspath(path)
		path = urlparse.urljoin('file:', urllib.pathname2url(path))
		
		# Load video
		self.load(path)		

		# Set handler of frames and user unput
		if self.has("canvas_backend"):
			if self.get("canvas_backend") == "legacy":				
				self.handler = legacy_handler(self, self.experiment.surface, custom_event_handler)
			if self.get("canvas_backend") == "psycho":				
				self.handler = psychopy_handler(self, self.experiment.window, custom_event_handler)
		else:
			# Give a sensible error message if the proper back-end has not been selected
			raise osexception("The media_player plug-in requires the legacy back-end. Sorry!")		
	
		# Report success
		return True

	def load(self, vfile):
		"""
		Loads a videofile and makes it ready for playback

		Arguments:
		file -- the path tp the file to be played
		"""
		# Info required for color space conversion (YUV->RGB)
		# masks are necessary for correct display on unix systems
		self._VIDEO_CAPS = ','.join([
		    'video/x-raw-rgb',
		    'red_mask=(int)0xff0000',
		    'green_mask=(int)0x00ff00',
		    'blue_mask=(int)0x0000ff',
		])

		caps = gst.Caps(self._VIDEO_CAPS)

		# Create videoplayer and load URI
		self.player = gst.element_factory_make("playbin2", "player")		
		self.player.set_property("uri", vfile)
		
		# Enable deinterlacing of video if necessary
		self.player.props.flags |= (1 << 9)		
		
		# Reroute frame output to Python
		self._videosink = gst.element_factory_make('appsink', 'videosink')		
		self._videosink.set_property('caps', caps)
		self._videosink.set_property('sync', True)
		self._videosink.set_property('drop', True)
		self._videosink.set_property('emit-signals', True)
		self._videosink.connect('new-buffer', self.handle_videoframe)		
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
				for name in caps.keys():
					print "{0}: {1}".format(name,caps[name])
				self.vidsize = caps['width'], caps['height']

		else:
			raise osexception("Failed to retrieve video size")
	
		if self.playaudio == "no":
			self.player.set_property("mute",True)				
					
		self.file_loaded = True
		
		if self.fullscreen == "yes":
			self.destsize = self.calcScaledRes((self.experiment.width,self.experiment.height), self.vidsize)				
		else:
			self.destsize = self.vidsize

		self.vidPos = ((self.experiment.width - self.destsize[0]) / 2, (self.experiment.height - self.destsize[1]) / 2)		
		
		# Calculate required buffer length		
		self.ReqBufferLength = self.vidsize[0] * self.vidsize[1] * 3	
		
		
	def handle_videoframe(self, appsink):
		buffer = appsink.emit('pull-buffer')
		
		# Get timestamp of player
		playtime = self.player.query_position(gst.FORMAT_TIME, None)[0]	

		# increment frame counter
		self.frame_no += 1
		
		# Send frame buffer to handler. Catch exceptions so that events can still
		# be handled regardless of error (makes it impossible to escape experiment with ESC otherwise)
		if playtime-buffer.timestamp < 10000000:
			try:
				self.handler.handle_videoframe(buffer.data)
			except Exception as e:
				print e
		else:
			return
		
		# Handle key and mouse presses after drawing frame to backbuffer
		if self._event_handler_always:
			self.playing = self.handler.process_user_input_customized()
		elif not self._event_handler_always:				
			self.playing = self.handler.process_user_input()
			
		# Only flip buffers now, so users have the ability to draw
		# on top of the videoframe in the custom event code
		self.handler.flip()
		
	
	def __adjust_videosize(self, (w,h)):				
		newcaps = self._VIDEO_CAPS + ', width=%d, height=%d' % (w,h)		
		caps = gst.Caps(newcaps)
		self._videosink.set_property('caps', caps)
		
		# Preroll movie to get dimension data
		self.vidsize = (w,h)
		self.ReqBufferLength = w * h * 3	
		
	def __on_message(self, bus, message):
		t = message.type		
		if t == gst.MESSAGE_EOS:
			self.player.set_state(gst.STATE_NULL)	
			self.gst_loop.quit()
		elif t == gst.MESSAGE_ERROR:
			self.player.set_state(gst.STATE_NULL)
			err, debug = message.parse_error()
			self.gst_loop.quit()
			raise osexception("Gst Error: %s" % err, debug)			

	def pause(self):
		"""Pauses playback"""
		if not self.paused:
			self.paused = True
			self.player.set_state(gst.STATE_PAUSED)

	def unpause(self):
		"""Continues playback"""
		if self.paused:
			self.paused = False
			self.player.set_state(gst.STATE_PLAYING)

	
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
			# Start gst loop (which listens for events from the player)
			thread.start_new_thread(self.gst_loop.run, ())						
			
			# Wait for gst loop to start running, but do so for a max of 50ms		
			counter = 0
			while not self.gst_loop.is_running():
				time.sleep(0.005)
				counter += 1
				if counter > 10:
					raise osexception("ERROR: gst loop failed to start")
			
			# Signal player to start video playback
			self.player.set_state(gst.STATE_PLAYING)			
						
			self.playing = True
			start_time = time.time()

			while self.playing:							
				if not self.paused:					
					self.handler.draw_buffer()
					
					if self.sendInfoToEyelink == "yes" and hasattr(self.experiment,"eyelink") and self.experiment.eyelink.connected():						
						self.experiment.eyelink.log("videoframe %s" % self.frame_no)
						self.experiment.eyelink.status_msg("videoframe %s" % self.frame_no )
								
				# Determine if playback should continue and handle events
				if type(self.duration) == int:
					if time.time() - start_time > self.duration:
						self.playing = False

				# Prevent overflow of event queue (window shows 'unresponsive' otherwise)				
				self.handler.pump_events()						
													
				if not self.gst_loop.is_running():
					self.playing = False				
			
			# Clean up resources
			self.close_streams()

			libopensesame.generic_response.generic_response.response_bookkeeping(self)			
			return True

		else:
			raise osexception("No video loaded")
			return False

	def close_streams(self):
	
		"""
		A cleanup function, to make sure that the video files are closed

		Returns:
		True on success, False on failure
		"""
		if self.gst_loop.is_running():		
			# Quit the player's main event loop
			self.gst_loop.quit()
			# Free resources claimed by gstreamer
			self.player.set_state(gst.STATE_NULL)
		
		if hasattr(self, "handler"):		
			del(self.handler)
		
		return True
		

	def var_info(self):

		return libopensesame.generic_response.generic_response.var_info(self)		

class qtmedia_player_gst(media_player_gst, qtplugin.qtplugin):

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
		media_player_gst.__init__(self, name, experiment, string)
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

