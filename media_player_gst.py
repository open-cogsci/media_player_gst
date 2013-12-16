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

This module interfaces with the GStreamer framework through the 
Python bindings supplied with it. The module enables media playback functionality 
in the OpenSesame Experiment buider. In this module's current version, the 
GStreamer SDK (from http://www.gstreamer.com) is expected to be 
installed at its default location (in windows this is c:\gstreamer-sdk). 
If this is not the case in your situation, please change the GSTREAMER_PATH 
variable so that it points to the location at which you installed the 
GStreamer framework. This plugin should then automatically find all required
libraries and Python modules.
"""

__author__ = "Daniel Schreij"
__license__ = "GPLv3"

import os, sys
import thread			# To run the gst event loop with
import time
import urlparse, urllib		# To build the URI that gst requires

# Import OpenSesame specific items
from libopensesame import item, debug, generic_response
from libopensesame.exceptions import osexception
from libqtopensesame import qtplugin, pool_widget
from libqtopensesame.items.qtautoplugin import qtautoplugin

# Gstreamer components

# If The Gstreamer SDK is found in the plugin folder, add the relevant paths
# so that we use this framework. This is Windows only.
if os.name == "nt":
	if os.path.exists(os.path.join(os.path.dirname(__file__), \
		'gstreamer-sdk')):
		GSTREAMER_PATH = os.path.join(os.path.dirname(__file__), \
		'gstreamer-sdk')
	else:
		GSTREAMER_PATH = r"C:\gstreamer-sdk"
	os.environ['PATH'] = os.path.join(GSTREAMER_PATH, '0.10', 'x86', 'bin') + \
		';' + os.environ['PATH']
	sys.path.append(os.path.join(GSTREAMER_PATH, '0.10','x86','lib', \
		'python2.7','site-packages'))
		
# Try to load Gstreamer
try:
	import gobject
	import pygst
	pygst.require("0.10")
	import gst
except:
	raise osexception("OpenSesame could not find the GStreamer framework!")

# Rendering components
import pygame
import psychopy


#---------------------------------------------------------------------
# Base classes (should be subclassed by backend-specific classes)
#---------------------------------------------------------------------

class pygame_handler(object):
	"""
	Superclass for both the legacy and expyriment hanlders. Both these backends are based on pygame, so have 
	the same event handling methods, which they can both inherit from this class.
	"""
	
	def __init__(self, main_player, screen, custom_event_code = None):
		"""
		Constructor. Set variables to be used in rest of class.

		Arguments:
		main_player -- reference to the main_player_gst object (which instantiates this class or its sublass)
		screen -- reference to the pygame display surface		

		Keyword arguments:
		custom_event_code -- (Compiled) code that is to be called after every frame
		"""		
		self.main_player = main_player
		self.screen = screen
		self.custom_event_code = custom_event_code	
	
	def handle_videoframe(self, frame, frame_on_time):
		"""
		Callback method for handling a video frame

		Arguments:
		frame - the video frame supplied as a str/bytes object
		frame_on_time - (True|False) indicates if renderer is lagging behind
			internal frame counter of the player (False) or is still in sync (True)
		"""	
		self.frame = frame	
		self.frame_on_time = frame_on_time
		
	def swap_buffers(self):
		"""
		Flips back and front buffers
		"""
		pygame.display.flip()
	
	def prepare_for_playback(self):
		"""
		Dummy function (to be implemented in OpenGL based subclasses like expyriment)
		This function should prepare the context of OpenGL based backends for playback
		"""
		pass
	
	def playback_finished(self):
		"""
		Dummy function (to be implemented in OpenGL based subclasses like expyriment)
		This function should restore OpenGL context to as it was before playback
		"""
		pass
			
	def process_user_input(self):
		"""
		Process events from input devices
		
		Returns:
		True -- if no key/mouse button has been pressed or if custom event code returns True
		False -- if a keypress or mouse click was detected (an OS indicates playback should be stopped then
			or custom event code has returned False
		"""

		for event in pygame.event.get():
			if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
				# Catch escape presses
				if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
					self.main_player.playing = False
					raise osexception(u"The escape key was pressed")				
				
				if self.custom_event_code != None:
					if event.type == pygame.KEYDOWN:
						return self.process_user_input_customized(("key", pygame.key.name(event.key)))
					elif event.type == pygame.MOUSEBUTTONDOWN:
						return self.process_user_input_customized(("mouse", event.button))	
				# Stop experiment on keypress (if indicated as stopping method)
				elif event.type == pygame.KEYDOWN and self.main_player.duration == u"keypress":					
					self.main_player.experiment.response = pygame.key.name(event.key)
					self.main_player.experiment.end_response_interval = pygame.time.get_ticks()
					return False
				# Stop experiment on mouse click (if indicated as stopping method)
				elif event.type == pygame.MOUSEBUTTONDOWN and self.main_player.duration == u"mouseclick":					
					self.main_player.experiment.response = event.button
					self.main_player.experiment.end_response_interval = pygame.time.get_ticks()
					return False	
		
		pygame.event.pump()
		return True

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
					raise osexception(u"The escape key was pressed")								
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

		# Variables for user to use in custom script
		exp = self.main_player.experiment
		frame = self.main_player.frame_no
		mov_width = self.main_player.destsize[0]
		mov_height = self.main_player.destsize[1]
		times_played = self.main_player.times_played
		
		# Easily callable pause function
		# Use can now simply say pause() und unpause()

		paused = self.main_player.paused # for checking if player is currently paused or not
		pause = self.main_player.pause

		# Add more convenience functions?

		try:
			exec(self.custom_event_code)
		except Exception as e:
			self.main_player.playing = False
			raise osexception(u"Error while executing event handling code: %s" % e)

		if type(continue_playback) != bool:
			continue_playback = False

		pygame.event.pump()
		return continue_playback


class OpenGL_renderer(object):
	"""
	Superclass for both the expyriment and psychopy handlers. Both these backends 
	are OpenGL based and basically have the same drawing routines. 
	This way they only need to be defined once for both classes.
	"""
	
	def __init__(self):
		raise osexception("This class should only be subclassed on not be instantiated directly!")
	
	def prepare_for_playback(self):
		"""Prepares the OpenGL context for playback"""
		GL = self.GL
				
		# Prepare OpenGL for drawing
		GL.glPushMatrix()		# Save current OpenGL context
		GL.glLoadIdentity()				

		# Set screen coordinates to useful values for movie playback (per pixel coordinates)
		GL.glMatrixMode(GL.GL_PROJECTION)
		GL.glPushMatrix()
		GL.glLoadIdentity()
		GL.glOrtho(0.0,  self.main_player.experiment.width,  self.main_player.experiment.height, 0.0, 0.0, 1.0)		
		GL.glMatrixMode(GL.GL_MODELVIEW)
		
	def playback_finished(self):
		""" Restore previous OpenGL context as before playback """
		GL = self.GL
		
		GL.glMatrixMode(GL.GL_PROJECTION)
		GL.glPopMatrix()
		GL.glMatrixMode(GL.GL_MODELVIEW)				
		GL.glPopMatrix()
		
	def draw_frame(self):		
		"""
		Does the actual rendering of the buffer to the screen
		"""	
		GL = self.GL

		# Get desired format from main player
		(w,h) = self.main_player.destsize
		(x,y) = self.main_player.vidPos						
					
		# Frame should blend with color white
		GL.glColor4f(1,1,1,1)
						
		# Only if a frame has been set, blit it to the texture
		if hasattr(self,"frame") and not self.frame is None:			    	
			texture_width = self.main_player.vidsize[0]
			texture_height = self.main_player.vidsize[1]
	
			GL.glClear(GL.GL_COLOR_BUFFER_BIT|GL.GL_DEPTH_BUFFER_BIT)	
			GL.glLoadIdentity()
		
			GL.glEnable(GL.GL_TEXTURE_2D)
		
			GL.glBindTexture(GL.GL_TEXTURE_2D, self.texid)
			GL.glTexImage2D( GL.GL_TEXTURE_2D, 0, GL.GL_RGB, texture_width, texture_height, 0,
				      GL.GL_RGB, GL.GL_UNSIGNED_BYTE, self.frame );
			GL.glTexParameterf(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
			GL.glTexParameterf(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)	
			
		# Drawing of the quad on which the frame texture is projected
		GL.glBegin(GL.GL_QUADS)
		GL.glTexCoord2f(0.0, 0.0); GL.glVertex3i(x, y, 0)
		GL.glTexCoord2f(1.0, 0.0); GL.glVertex3i(x+w, y, 0)
		GL.glTexCoord2f(1.0, 1.0); GL.glVertex3i(x+w, y+h, 0)
		GL.glTexCoord2f(0.0, 1.0); GL.glVertex3i(x, y+h, 0)				
		GL.glEnd()
		
		# Make sure there are no pending drawing operations and flip front and backbuffer
		GL.glFlush()

		
#---------------------------------------------------------------------
# Backend specific classes
#---------------------------------------------------------------------	

class legacy_handler(pygame_handler):
	"""
	Handles video frames and input supplied by media_player_gst for the legacy backend, which is based on pygame
	"""
	
	def __init__(self, main_player, screen, custom_event_code = None):
		"""
		Constructor. Set variables to be used in rest of class.

		Arguments:
		main_player -- reference to the main_player_gst object (which should instantiate this class)
		screen -- reference to the pygame display surface		

		Keyword arguments:
		custom_event_code -- (Compiled) code that is to be called after every frame
		"""	
		# Call constructor of super class
		super(legacy_handler, self).__init__(main_player, screen, custom_event_code )		
				
		# Already create surfaces so this does not need to be redone for every frame
		# The time to process a single frame should be much shorter this way.				
		self.img = pygame.Surface(self.main_player.vidsize, pygame.SWSURFACE, 24, (255, 65280, 16711680, 0))
		# Create pygame bufferproxy object for direct surface access
		# This saves us from using the time consuming pygame.image.fromstring() method as the frame will be
		# supplied in a format that can be written directly to the bufferproxy		
		self.imgBuffer = self.img.get_buffer()
		if self.main_player.fullscreen == u"yes":			
			self.dest_surface = pygame.Surface(self.main_player.destsize, pygame.SWSURFACE, 24, (255, 65280, 16711680, 0))		
		
	def prepare_for_playback(self):
		"""
		Just fills the screen with the background color for this backend
		"""
		# Fill surface with background color
		self.screen.fill(pygame.Color(str(self.main_player.experiment.background)))
		self.last_drawn_frame_no = 0
	
	def draw_frame(self):
		"""
		Does the actual rendering of the buffer to the screen
		"""	
		
		if hasattr(self,"frame") and not self.frame is None:			
			# Only draw frame to screen if timestamp is still within bounds of that of the player                
			# Just skip the drawing otherwise (and continue until a frame comes in that is in bounds again)
			# Additionally, only draw each frame to screen once, to give the pygame (software-based) rendering engine
			# some breathing space
			
			if self.frame_on_time and self.last_drawn_frame_no != self.main_player.frame_no:
				# Write the video frame to the bufferproxy
				self.imgBuffer.write(self.frame, 0)
				
				# If resize option is selected, resize frame to screen/window dimensions and blit
				if hasattr(self, "dest_surface"):
					pygame.transform.scale(self.img, self.main_player.destsize, self.dest_surface)
					self.screen.blit(self.dest_surface, self.main_player.vidPos)
				else:	
				# In case movie needs to be displayed 1-on-1 blit directly to screen
					self.screen.blit(self.img.copy(), self.main_player.vidPos)		
				#self.swap_buffers()
				self.last_drawn_frame_no = self.main_player.frame_no
	
		
class expyriment_handler(OpenGL_renderer, pygame_handler):
	"""
	Handles video frames and input supplied by media_player_gst for the expyriment backend, 
	which is based on pygame (with OpenGL in fullscreen mode)
	"""
	def __init__(self, main_player, screen, custom_event_code = None):
		import OpenGL.GL as GL
		
		# Initialize super c lass
		pygame_handler.__init__(self, main_player, screen, custom_event_code )
		
		# GL context to use by the OpenGL_renderer class
		self.GL = GL
		self.texid = GL.glGenTextures(1)	
		
		
class psychopy_handler(OpenGL_renderer):
	"""
	Handles video frames and input for the psychopy backend supplied by media_player_gst
	Based on OpenGL so inherits from the OpenGL_renderer superclass
	"""
	def __init__(self, main_player, screen, custom_event_code = None):
		"""
		Constructor. Set variables to be used in rest of class.

		Arguments:
		main_player -- reference to the main_player_gst object (which should instantiate this class)
		screen -- reference to the pygame display surface		

		Keyword arguments:
		custom_event_code -- (Compiled) code that is to be called after every frame
		"""		
		import ctypes
		import pyglet.gl		
		
		self.main_player = main_player
		self.win = screen
		self.frame = None
		self.custom_event_code = custom_event_code	

		# GL context to be used by the OpenGL_renderer class
		# Create texture to render frames to later
		GL = self.GL = pyglet.gl	
		self.texid = GL.GLuint()
		GL.glGenTextures(1, ctypes.byref(self.texid))
					
	def handle_videoframe(self, frame, frame_on_time):
		"""
		Callback method for handling a video frame

		Arguments:
		frame - the video frame supplied as a str/bytes object
		frame_on_time - (True|False) indicates if renderer is lagging behind
			internal frame counter of the player (False) or is still in sync (True)
		"""		
		self.frame = frame
		self.frame_on_time = frame_on_time
		
	def swap_buffers(self):
		"""Draw buffer to screen"""
		self.win.flip()
		
	def process_user_input(self):		
		"""
		Process events from input devices
		
		Returns:
		True -- if no key/mouse button has been pressed or if custom event code returns True
		False -- if a keypress or mouse click was detected (an OS indicates playback should be stopped then
			or custom event code has returned False
		"""		
		pressed_keys = psychopy.event.getKeys()				
		
		for key in pressed_keys:				
			# Catch escape presses
			if key == "escape":
				self.main_player.playing = False
				raise osexception("The escape key was pressed")	
	
			if self.custom_event_code != None:
				return self.process_user_input_customized(("key", key))				
			elif self.main_player.duration == u"keypress":
				self.main_player.experiment.response = key
				self.main_player.experiment.end_response_interval = time.time()	
				return False		
		return True
						
		
	def process_user_input_customized(self, event=None):
		"""
		Allows the user to insert custom code. Code is stored in the event_handler variable.

		Arguments:
		event -- a tuple containing the type of event (key or mouse button press)
			   and the value of the key or mouse button pressed (which character or mouse button)
		"""
	
		if event is None:
			events = psychopy.event.getKeys()
			event = []  # List to contain collected info on key and mouse presses			
			for key in events:
				if key == "escape":
					self.main_player.playing = False
					raise osexception(u"The escape key was pressed")								
				else:
					event.append(("key", key))

			# If there is only one tuple in the list of collected events, take it out of the list 
			if len(event) == 1:
				event = event[0]		
		
		
		continue_playback = True		
	
		# Variables for user to use in custom script
		exp = self.main_player.experiment		
		frame = self.main_player.frame_no
		mov_width = self.main_player.destsize[0]
		mov_height = self.main_player.destsize[1]
		times_played = self.main_player.times_played
		
		# Easily callable pause function
		# Use can now simply call pause() to pause and unpause()
		paused = self.main_player.paused
		pause = self.main_player.pause

		# Add more convenience functions?	
		
		# Execute custom code
		try:
			exec(self.custom_event_code)
		except Exception as e:
			self.main_player.playing = False
			raise osexception(u"Error while executing event handling code: %s" % e)

		# if continue_playback has been set to anything else than True or False, then stop playback
		if type(continue_playback) != bool:
			continue_playback = False	
		
		return continue_playback
	
#---------------------------------------------------------------------
# Main player class -- communicates with GStreamer
#---------------------------------------------------------------------

class media_player_gst(item.item, generic_response.generic_response):

	"""The media_player plug-in offers advanced video playback functionality in OpenSesame using the GStreamer framework"""

	def __init__(self, name, experiment, string = None):
		"""
		Constructor. 

		Arguments:
		name -- the name of the item
		experiment -- the opensesame experiment

		Keyword arguments:
		string -- a definition string for the item (Default = None)
		"""

		# The version of the plug-in
		self.version = "1.0"

		# GUI config options		
		self.item_type = u"media_player"
		self.description = u"Plays a video from file"
		self.video_src = ""
		self.duration = u"keypress"
		self.fullscreen = u"yes"
		self.playaudio = u"yes"
		self.sendInfoToEyelink = u"no"
		self.loop = u"no"
		self.event_handler_trigger = u"on keypress"
		self.event_handler = u""				
		
		# The parent handles the rest of the construction
		item.item.__init__(self, name, experiment, string)

		# Indicate function for clean up that is run after the experiment finishes
		self.experiment.cleanup_functions.append(self.close_streams)
	
	def calculate_scaled_resolution(self, screen_res, image_res):
		"""Calculate image size so it fits the screen
		Arguments:
		screen_res  --  Tuple containing display window size/Resolution
		image_res   --  Tuple containing image width and height
			
		Returns:
		(width, height) tuple of image scaled to window/screen
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

		# Prepare GST loop
		gobject.threads_init()
		self.gst_loop = gobject.MainLoop()	
		
		# Start gst loop (does internal gst event handling)
		thread.start_new_thread(self.gst_loop.run, ())	
		
		# class variables
		self.frame_no = 0		# The no of the current frame
		self.frames_displayed = 0	# To determine how many frames have been dropped
		self.times_played = 1		# When in loop mode, this variable maintains the times looped

		# Byte-compile the event handling code (if any)
		if self.event_handler.strip() != "":
			custom_event_handler = compile(self.event_handler, "<string>", "exec")
		else:
			custom_event_handler = None

		# Determine when the event handler should be called
		if self.event_handler_trigger == u"on keypress":
			self._event_handler_always = False
		else:
			self._event_handler_always = True				

		# Find the full path to the video file. This will point to some
		# temporary folder where the file pool has been placed
		path = self.experiment.get_file(str(self.eval_text(self.get("video_src"))))
		
		# Open the video file
		if not os.path.exists(path) or str(self.eval_text("video_src")).strip() == "":
			raise osexception(u"Video file '%s' was not found in video_player '%s' (or no video file was specified)." % (os.path.basename(path), self.name))
		
		debug.msg(u"media_player_gst.prepare(): loading '%s'" % path)
		
		# Determine URI to file source
		path = os.path.abspath(path)
		path = urlparse.urljoin('file:', urllib.pathname2url(path))
		
		debug.msg(u"transformed to URI '%s'" % path)		
		
		# Load video
		self.load(path)		

		# Set handler of frames and user input
		if self.has("canvas_backend"):
			if self.get("canvas_backend") == u"legacy":				
				self.handler = legacy_handler(self, self.experiment.surface, custom_event_handler)
			if self.get("canvas_backend") == u"psycho":				
				self.handler = psychopy_handler(self, self.experiment.window, custom_event_handler)
			if self.get("canvas_backend") == u"xpyriment":			
				# Expyriment uses OpenGL in fullscreen mode, but just pygame 
				# (legacy) display mode otherwise
				if self.experiment.fullscreen:				
					self.handler = expyriment_handler(self, self.experiment.window, custom_event_handler)
				else:
					self.handler = legacy_handler(self, self.experiment.window, custom_event_handler)
		else:
			# Give a sensible error message if the proper back-end has not been selected
			raise osexception(u"The media_player plug-in could not determine which backend was used!")		
	
		# Report success		
	
		return True

	def load(self, vfile):
		"""
		Loads a videofile and makes it ready for playback

		Arguments:
		vfile -- the path to the file to be played
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
		self._videosink.set_property('async', True)
		self._videosink.set_property('drop', True)
		self._videosink.set_property('emit-signals', True)
		
		# Here the frame output is linked to our custom callback function
		# which further processes the frame contents
		self._videosink.connect('new-buffer', self.__handle_videoframe)		
		
		# Let the player output to our just created videosink
		self.player.set_property('video-sink', self._videosink)

		# Set functions for handling player messages
		self.bus = self.player.get_bus()		
		#self.bus.enable_sync_message_emission()
		#bus.add_signal_watch()
		#bus.connect("message", self.__on_message)
		
		# Preroll movie to get dimension data
		self.player.set_state(gst.STATE_PAUSED)
		
		# If movie is loaded correctly, info about the clip should be available
		if self.player.get_state(gst.CLOCK_TIME_NONE)[0] == gst.STATE_CHANGE_SUCCESS:
			pads = self._videosink.pads()			
			for pad in pads:		
				caps = pad.get_negotiated_caps()[0]
				for name in caps.keys():
					debug.msg(u"{0}: {1}".format(name,caps[name]))
					
				# Video dimensions
				self.vidsize = caps['width'], caps['height']				
				# Frame rate
				fps = caps["framerate"]
				self.fps = (1.0*fps.num/fps.denom)

		else:
			raise osexception(u"Failed to open movie. Do you have all the necessary codecs/plugins installed?")
	
		# Mute audio if necessary
		if self.playaudio == u"no":
			self.player.set_property("mute", True)				
					
		if self.fullscreen == u"yes":
			# Calculate dimensions of video when scaled up to screen dimensions
			self.destsize = self.calculate_scaled_resolution((self.experiment.width,self.experiment.height), self.vidsize)				
		else:
			# If no scaling is required, just use the original video dimensions for the destination size
			self.destsize = self.vidsize

		# x,y coordinate of top-left video corner
		self.vidPos = ((self.experiment.width - self.destsize[0]) / 2, (self.experiment.height - self.destsize[1]) / 2)		
		self.file_loaded = True	
		
	def __handle_videoframe(self, appsink):
		# Get buffer from videosink
		buffer = appsink.emit('pull-buffer')
							
		# increment frame counter
		self.frame_no += 1

		# Check if the timestamp of the buffer is not too far behind on the internal clock of the player
		# If computer is too slow for playing HD movies for instance, we need to drop frames 'manually'		
		frame_on_time = self.player.query_position(gst.FORMAT_TIME, None)[0] - buffer.timestamp < 250000000
		
		# Increase counter of frames displayed, to calculate real FPS at end of playback
		if frame_on_time:
			self.frames_displayed += 1
								
		# Send frame buffer to handler. Let it decide whether to show the video frame or not
		# (OpenGL based handlers will always  be on time so frames will unlikely need to be dropped there)
		self.handler.handle_videoframe(buffer.data, frame_on_time)	

	def pause(self):
		""" 
		Function to pause or resume playback (like a toggle). Checks the paused variable for the player's current status.
		If this function is called when playing the playback will be paused. If the playback was paused 
		a call to this function will resume it
		"""
		if self.paused:
			self.player.set_state(gst.STATE_PLAYING)
			self.paused = False			
		elif not self.paused:		
			self.player.set_state(gst.STATE_PAUSED)
			self.paused = True			
	
	def run(self):
		"""
		Starts the playback of the video file. You can specify an optional callable object to handle events between frames (like keypresses)
		This function needs to return a boolean, because it determines if playback is continued or stopped. Playback will still stop when the ESC key is pressed.

		Returns:
		True on success, False on failure
		"""
		
		debug.msg(u"Starting video playback")
                
		# Log the onset time of the item
		self.set_item_onset()

		# Set some response variables, in case a response will be given
		if self.experiment.start_response_interval == None:
			self.experiment.start_response_interval = self.get("time_%s" % self.name)
			self.experiment.end_response_interval = self.experiment.start_response_interval
		self.experiment.response = None

		if self.file_loaded:							
			# Signal player to start video playback
			self.player.set_state(gst.STATE_PLAYING)		
			
			self.playing = True
			self.paused = False
			
			# Prepare frame renderer in handler for playback
			# (e.g. set up OpenGL context, thus only relevant for OpenGL based backends)
			self.handler.prepare_for_playback()

			### Main player loop. While True, the movie is playing
			start_time = time.time()
			while self.playing:
				# Draw current frame to screen
				self.handler.draw_frame()
				
				# TODO: add section to let user optionally draw stuff on top of frame				
				# Best is to advise them to use the frame_no				
				
				# Swap buffers to show drawn stuff on screen
				self.handler.swap_buffers()
					
				if not self.paused:						
					# If connected to EyeLink and indicated that frame info should be sent.												
					if self.sendInfoToEyelink == u"yes" and hasattr(self.experiment,"eyelink") and self.experiment.eyelink.connected():						
						self.experiment.eyelink.log(u"videoframe %s" % self.frame_no)
						self.experiment.eyelink.status_msg(u"videoframe %s" % self.frame_no )
				
				# Listen for events 								
				if self._event_handler_always:
					self.playing = self.handler.process_user_input_customized()
				elif not self._event_handler_always:				
					self.playing = self.handler.process_user_input()
								
				# Determine if playback should continue when a time limit is set
				if type(self.duration) == int:
					if time.time() - start_time > self.duration:
						self.playing = False				
								
				# Check for GST events: End of stream and errors
	
				if self.bus.peek():
					event = self.bus.poll(gst.MESSAGE_EOS|gst.MESSAGE_ERROR, 1)
					if event:				
						if event.type == gst.MESSAGE_EOS:
							if self.loop == "yes":
								# Seek to the beginning of the movie again and keep playing
								self.player.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, 1.0)
								self.times_played += 1
							else:
								# Stop the player and quit the gst mainloop
								self.playing = False
						elif event.type == gst.MESSAGE_ERROR:
							err, debug_info = event.parse_error()
							print u"Gst Error: %s" % err, debug_info
							self.close_streams()
							raise osexception(u"Gst Error: %s" % err, debug_info)
																							
				# If gst loop is not running stop playback					
				if not self.gst_loop.is_running():
					self.playing = False								
				
			# Restore OpenGL context as before playback
			self.handler.playback_finished()
									
			# Clean up resources					
			self.close_streams()
			
			# Register real frames per second
			fps_prop = 1.0 *self.frames_displayed/self.frame_no
			real_fps =  self.fps * fps_prop 			
			debug.msg(u"Movie displayed with {0} fps ({1}% of intended {2} fps)".format(round(real_fps,2), int(fps_prop*100), round(self.fps,2)))

			# Do some OpenSesame bookkeeping concerning responses
			generic_response.generic_response.response_bookkeeping(self)			
			return True
		else:
			raise osexception(u"No video loaded")

	def close_streams(self):
	
		"""
		A cleanup function, to make sure that the video files are closed

		Returns:
		True on success
		"""
		if self.gst_loop.is_running():	
			# Free resources claimed by gstreamer
			self.player.set_state(gst.STATE_NULL)
			# Quit the player's main event loop
			self.gst_loop.quit()

		
		return True
	
#	def __on_message(self, bus, message):	
#		"""
#		GStreamer callback function that listens from messages from the bus
#		
#		Arguments
#		bus -- The GStreamer bus element from which the message originates
#		message -- the object containing the message information
#		"""	
#		# determine type of message
#		t = message.type		
#		print t
#		
#		# If end of movie has been reached
#		if t == gst.MESSAGE_EOS:
#			if self.loop == "yes":
#				# Seek to the beginning of the movie again and keep playing
#				self.player.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, 1.0)
#			else:
#				# Stop the player and quit the gst mainloop
#				self.player.set_state(gst.STATE_NULL)	
#				self.gst_loop.quit()
#		
#		# If an error message has been received 
#		# (does not quite work yet as error messages are not correctly shown in OpenSesame)
#		elif t == gst.MESSAGE_ERROR:
#			err, debug_info = message.parse_error()
#			print u"Gst Error: %s" % err, debug_info
#			self.player.set_state(gst.STATE_NULL)
#			self.gst_loop.quit()
#			raise osexception(u"Gst Error: %s" % err, debug_info)	
		
	def var_info(self):
		return generic_response.generic_response.var_info(self)


#---------------------------------------------------------------------
# GUI class
#---------------------------------------------------------------------

class qtmedia_player_gst(media_player_gst, qtautoplugin):

	"""Handles the GUI aspects of the plug-in"""

	def __init__(self, name, experiment, script = None):

		"""
		Constructor.
		
		Arguments:
		name		--	The item name.
		experiment	--	The experiment object.
		
		Keyword arguments:
		script		--	The definition script. (default=None).
		"""

		# Pass the word on to the parents
		media_player_gst.__init__(self, name, experiment, script)
		qtautoplugin.__init__(self, __file__)

	def apply_edit_changes(self):
		
		"""Applies changes to the controls."""
		
		qtautoplugin.apply_edit_changes(self)
		# The duration field is enabled or disabled based on whether a custom
		# event handler is called or not.
		self.line_edit_duration.setEnabled( \
			self.combobox_event_handler_trigger.currentIndex() == 0)
