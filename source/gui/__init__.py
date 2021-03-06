#gui/__init__.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2011 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import time
import os
import sys
import threading
import codecs
import ctypes
import wx
import globalVars
import tones
import ui
from logHandler import log
import config
import versionInfo
import speech
import queueHandler
import core
from settingsDialogs import *
import speechDictHandler
import languageHandler
import logViewer
import speechViewer
import winUser
import api
try:
	import updateCheck
except RuntimeError:
	updateCheck = None

### Constants
NVDA_PATH = os.getcwdu()
ICON_PATH=os.path.join(NVDA_PATH, "images", "nvda.ico")
DONATE_URL = "http://www.nvaccess.org/wiki/Donate"

### Globals
mainFrame = None
isInMessageBox = False

def getDocFilePath(fileName, localized=True):
	if not getDocFilePath.rootPath:
		if hasattr(sys, "frozen"):
			getDocFilePath.rootPath = os.path.join(NVDA_PATH, "documentation")
		else:
			getDocFilePath.rootPath = os.path.abspath(os.path.join("..", "user_docs"))

	if localized:
		lang = languageHandler.getLanguage()
		tryLangs = [lang]
		if "_" in lang:
			# This locale has a sub-locale, but documentation might not exist for the sub-locale, so try stripping it.
			tryLangs.append(lang.split("_")[0])
		# If all else fails, use English.
		tryLangs.append("en")

		fileName, fileExt = os.path.splitext(fileName)
		for tryLang in tryLangs:
			tryDir = os.path.join(getDocFilePath.rootPath, tryLang)
			if not os.path.isdir(tryDir):
				continue

			# Some out of date translations might include .txt files which are now .html files in newer translations.
			# Therefore, ignore the extension and try both .html and .txt.
			for tryExt in ("html", "txt"):
				tryPath = os.path.join(tryDir, "%s.%s" % (fileName, tryExt))
				if os.path.isfile(tryPath):
					return tryPath

	else:
		# Not localized.
		if not hasattr(sys, "frozen") and fileName in ("copying.txt", "contributors.txt"):
			# If running from source, these two files are in the root dir.
			return os.path.join(NVDA_PATH, "..", fileName)
		else:
			return os.path.join(getDocFilePath.rootPath, fileName)
getDocFilePath.rootPath = None

class MainFrame(wx.Frame):

	def __init__(self):
		style = wx.DEFAULT_FRAME_STYLE ^ wx.MAXIMIZE_BOX ^ wx.MINIMIZE_BOX | wx.FRAME_NO_TASKBAR
		super(MainFrame, self).__init__(None, wx.ID_ANY, versionInfo.name, size=(1,1), style=style)
		self.Bind(wx.EVT_CLOSE, self.onExitCommand)
		self.sysTrayIcon = SysTrayIcon(self)
		# This makes Windows return to the previous foreground window and also seems to allow NVDA to be brought to the foreground.
		self.Show()
		self.Hide()
		if winUser.isWindowVisible(self.Handle):
			# HACK: Work around a wx bug where Hide() doesn't actually hide the window,
			# but IsShown() returns False and Hide() again doesn't fix it.
			# This seems to happen if the call takes too long.
			self.Show()
			self.Hide()

	def Destroy(self):
		self.sysTrayIcon.Destroy()
		super(MainFrame, self).Destroy()

	def prePopup(self):
		"""Prepare for a popup.
		This should be called before any dialog or menu which should pop up for the user.
		L{postPopup} should be called after the dialog or menu has been shown.
		@postcondition: A dialog or menu may be shown.
		"""
		if winUser.getWindowThreadProcessID(winUser.getForegroundWindow())[0] != os.getpid():
			# This process is not the foreground process, so bring it to the foreground.
			self.Raise()

	def postPopup(self):
		"""Clean up after a popup dialog or menu.
		This should be called after a dialog or menu was popped up for the user.
		"""
		if not winUser.isWindowVisible(winUser.getForegroundWindow()):
			# The current foreground window is invisible, so we want to return to the previous foreground window.
			# Showing and hiding our main window seems to achieve this.
			self.Show()
			self.Hide()

	def showGui(self):
		# The menu pops up at the location of the mouse, which means it pops up at an unpredictable location.
		# Therefore, move the mouse to the centre of the screen so that the menu will always pop up there.
		left, top, width, height = api.getDesktopObject().location
		x = width / 2
		y = height / 2
		winUser.setCursorPos(x, y)
		self.sysTrayIcon.onActivate(None)

	def onRevertToSavedConfigurationCommand(self,evt):
		queueHandler.queueFunction(queueHandler.eventQueue,core.resetConfiguration)
		queueHandler.queueFunction(queueHandler.eventQueue,ui.message,_("Configuration applied"))

	def onRevertToDefaultConfigurationCommand(self,evt):
		queueHandler.queueFunction(queueHandler.eventQueue,core.resetConfiguration,factoryDefaults=True)
		queueHandler.queueFunction(queueHandler.eventQueue,ui.message,_("Configuration restored to factory defaults"))

	def onSaveConfigurationCommand(self,evt):
		if globalVars.appArgs.secure:
			queueHandler.queueFunction(queueHandler.eventQueue,ui.message,_("Cannot save configuration - NVDA in secure mode"))
			return
		try:
			config.save()
			queueHandler.queueFunction(queueHandler.eventQueue,ui.message,_("Configuration saved"))
		except:
			messageBox(_("Could not save configuration - probably read only file system"),_("Error"),wx.OK | wx.ICON_ERROR)

	def _popupSettingsDialog(self, dialog, *args, **kwargs):
		if isInMessageBox:
			return
		self.prePopup()
		try:
			dialog(self, *args, **kwargs).Show()
		except SettingsDialog.MultiInstanceError:
			messageBox(_("Please close the other NVDA settings dialog first"),_("Error"),style=wx.OK | wx.ICON_ERROR)
		self.postPopup()

	def onDefaultDictionaryCommand(self,evt):
		self._popupSettingsDialog(DictionaryDialog,_("Default dictionary"),speechDictHandler.dictionaries["default"])

	def onVoiceDictionaryCommand(self,evt):
		self._popupSettingsDialog(DictionaryDialog,_("Voice dictionary (%s)")%speechDictHandler.dictionaries["voice"].fileName,speechDictHandler.dictionaries["voice"])

	def onTemporaryDictionaryCommand(self,evt):
		self._popupSettingsDialog(DictionaryDialog,_("Temporary dictionary"),speechDictHandler.dictionaries["temp"])

	def onExitCommand(self, evt):
		canExit=False
		if config.conf["general"]["askToExit"]:
			if isInMessageBox:
				return
			if messageBox(_("Are you sure you want to quit NVDA?"), _("Exit NVDA"), wx.YES_NO|wx.ICON_WARNING) == wx.YES:
				canExit=True
		else:
			canExit=True
		if canExit:
			wx.GetApp().ExitMainLoop()

	def onGeneralSettingsCommand(self,evt):
		self._popupSettingsDialog(GeneralSettingsDialog)

	def onSynthesizerCommand(self,evt):
		self._popupSettingsDialog(SynthesizerDialog)

	def onVoiceCommand(self,evt):
		self._popupSettingsDialog(VoiceSettingsDialog)

	def onBrailleCommand(self,evt):
		self._popupSettingsDialog(BrailleSettingsDialog)

	def onKeyboardSettingsCommand(self,evt):
		self._popupSettingsDialog(KeyboardSettingsDialog)

	def onMouseSettingsCommand(self,evt):
		self._popupSettingsDialog(MouseSettingsDialog)

	def onReviewCursorCommand(self,evt):
		self._popupSettingsDialog(ReviewCursorDialog)

	def onInputCompositionCommand(self,evt):
		self._popupSettingsDialog(InputCompositionDialog)

	def onObjectPresentationCommand(self,evt):
		self._popupSettingsDialog(ObjectPresentationDialog)

	def onBrowseModeCommand(self,evt):
		self._popupSettingsDialog(BrowseModeDialog)

	def onDocumentFormattingCommand(self,evt):
		self._popupSettingsDialog(DocumentFormattingDialog)

	def onSpeechSymbolsCommand(self, evt):
		self._popupSettingsDialog(SpeechSymbolsDialog)

	def onAboutCommand(self,evt):
		messageBox(versionInfo.aboutMessage, _("About NVDA"), wx.OK)

	def onCheckForUpdateCommand(self, evt):
		updateCheck.UpdateChecker().check()
		
	def onViewLogCommand(self, evt):
		logViewer.activate()

	def onToggleSpeechViewerCommand(self, evt):
		if not speechViewer.isActive:
			speechViewer.activate()
			self.sysTrayIcon.menu_tools_toggleSpeechViewer.Check(True)
		else:
			speechViewer.deactivate()
			self.sysTrayIcon.menu_tools_toggleSpeechViewer.Check(False)

	def onPythonConsoleCommand(self, evt):
		import pythonConsole
		if not pythonConsole.consoleUI:
			pythonConsole.initialize()
		pythonConsole.activate()

	def onAddonsManagerCommand(self,evt):
		if isInMessageBox:
			return
		self.prePopup()
		from addonGui import AddonsDialog
		d=AddonsDialog(gui.mainFrame)
		d.Show()
		self.postPopup()

	def onReloadPluginsCommand(self, evt):
		import appModuleHandler, globalPluginHandler
		from NVDAObjects import NVDAObject
		appModuleHandler.reloadAppModules()
		globalPluginHandler.reloadGlobalPlugins()
		NVDAObject.clearDynamicClassCache()

	def onCreatePortableCopyCommand(self,evt):
		if isInMessageBox:
			return
		self.prePopup()
		import gui.installerGui
		d=gui.installerGui.PortableCreaterDialog(gui.mainFrame)
		d.Show()
		self.postPopup()

	def onInstallCommand(self, evt):
		if isInMessageBox:
			return
		self.prePopup()
		from gui.installerGui import InstallerDialog
		import installer
		InstallerDialog(self).Show()
		self.postPopup()

class SysTrayIcon(wx.TaskBarIcon):

	def __init__(self, frame):
		super(SysTrayIcon, self).__init__()
		icon=wx.Icon(ICON_PATH,wx.BITMAP_TYPE_ICO)
		self.SetIcon(icon, versionInfo.name)

		self.menu=wx.Menu()
		menu_preferences=self.preferencesMenu=wx.Menu()
		item = menu_preferences.Append(wx.ID_ANY,_("&General settings..."),_("General settings"))
		self.Bind(wx.EVT_MENU, frame.onGeneralSettingsCommand, item)
		item = menu_preferences.Append(wx.ID_ANY,_("&Synthesizer..."),_("Change the synthesizer to be used"))
		self.Bind(wx.EVT_MENU, frame.onSynthesizerCommand, item)
		item = menu_preferences.Append(wx.ID_ANY,_("&Voice settings..."),_("Choose the voice, rate, pitch and volume to use"))
		self.Bind(wx.EVT_MENU, frame.onVoiceCommand, item)
		item = menu_preferences.Append(wx.ID_ANY,_("B&raille settings..."))
		self.Bind(wx.EVT_MENU, frame.onBrailleCommand, item)
		item = menu_preferences.Append(wx.ID_ANY,_("&Keyboard settings..."),_("Configure keyboard layout, speaking of typed characters, words or command keys"))
		self.Bind(wx.EVT_MENU, frame.onKeyboardSettingsCommand, item)
		item = menu_preferences.Append(wx.ID_ANY, _("&Mouse settings..."),_("Change reporting of mouse shape and object under mouse"))
		self.Bind(wx.EVT_MENU, frame.onMouseSettingsCommand, item)
		item = menu_preferences.Append(wx.ID_ANY,_("Review &cursor..."),_("Configure how and when the review cursor moves")) 
		self.Bind(wx.EVT_MENU, frame.onReviewCursorCommand, item)
		item = menu_preferences.Append(wx.ID_ANY,_("&Input composition settings..."),_("Configure how NVDA reports input composition and candidate selection for certain languages")) 
		self.Bind(wx.EVT_MENU, frame.onInputCompositionCommand, item)
		item = menu_preferences.Append(wx.ID_ANY,_("&Object presentation..."),_("Change reporting of objects")) 
		self.Bind(wx.EVT_MENU, frame.onObjectPresentationCommand, item)
		item = menu_preferences.Append(wx.ID_ANY,_("&Browse mode..."),_("Change virtual buffers specific settings")) 
		self.Bind(wx.EVT_MENU, frame.onBrowseModeCommand, item)
		item = menu_preferences.Append(wx.ID_ANY,_("Document &formatting..."),_("Change settings of document properties")) 
		self.Bind(wx.EVT_MENU, frame.onDocumentFormattingCommand, item)
		subMenu_speechDicts = wx.Menu()
		if not globalVars.appArgs.secure:
			item = subMenu_speechDicts.Append(wx.ID_ANY,_("&Default dictionary..."),_("A dialog where you can set default dictionary by adding dictionary entries to the list"))
			self.Bind(wx.EVT_MENU, frame.onDefaultDictionaryCommand, item)
			item = subMenu_speechDicts.Append(wx.ID_ANY,_("&Voice dictionary..."),_("A dialog where you can set voice-specific dictionary by adding dictionary entries to the list"))
			self.Bind(wx.EVT_MENU, frame.onVoiceDictionaryCommand, item)
		item = subMenu_speechDicts.Append(wx.ID_ANY,_("&Temporary dictionary..."),_("A dialog where you can set temporary dictionary by adding dictionary entries to the edit box"))
		self.Bind(wx.EVT_MENU, frame.onTemporaryDictionaryCommand, item)
		menu_preferences.AppendMenu(wx.ID_ANY,_("Speech &dictionaries"),subMenu_speechDicts)
		if not globalVars.appArgs.secure:
			item = menu_preferences.Append(wx.ID_ANY, _("&Punctuation/symbol pronunciation..."))
			self.Bind(wx.EVT_MENU, frame.onSpeechSymbolsCommand, item)
		self.menu.AppendMenu(wx.ID_ANY,_("&Preferences"),menu_preferences)

		menu_tools = self.toolsMenu = wx.Menu()
		if not globalVars.appArgs.secure:
			item = menu_tools.Append(wx.ID_ANY, _("View log"))
			self.Bind(wx.EVT_MENU, frame.onViewLogCommand, item)
		item=self.menu_tools_toggleSpeechViewer = menu_tools.AppendCheckItem(wx.ID_ANY, _("Speech viewer"))
		self.Bind(wx.EVT_MENU, frame.onToggleSpeechViewerCommand, item)
		if not globalVars.appArgs.secure:
			item = menu_tools.Append(wx.ID_ANY, _("Python console"))
			self.Bind(wx.EVT_MENU, frame.onPythonConsoleCommand, item)
			# Translators: The label of a menu item to open the Add-ons Manager.
			item = menu_tools.Append(wx.ID_ANY, _("Manage &add-ons"))
			self.Bind(wx.EVT_MENU, frame.onAddonsManagerCommand, item)
		if not globalVars.appArgs.secure and getattr(sys,'frozen',None):
			item = menu_tools.Append(wx.ID_ANY, _("Create Portable copy..."))
			self.Bind(wx.EVT_MENU, frame.onCreatePortableCopyCommand, item)
			if not config.isInstalledCopy():
				item = menu_tools.Append(wx.ID_ANY, _("&Install NVDA..."))
				self.Bind(wx.EVT_MENU, frame.onInstallCommand, item)
		item = menu_tools.Append(wx.ID_ANY, _("Reload plugins"))
		self.Bind(wx.EVT_MENU, frame.onReloadPluginsCommand, item)
		self.menu.AppendMenu(wx.ID_ANY, _("Tools"), menu_tools)

		menu_help = self.helpMenu = wx.Menu()
		if not globalVars.appArgs.secure:
			item = menu_help.Append(wx.ID_ANY, _("User Guide"))
			self.Bind(wx.EVT_MENU, lambda evt: os.startfile(getDocFilePath("userGuide.html")), item)
			# Translators: The label of a menu item to open the Commands Quick Reference document.
			item = menu_help.Append(wx.ID_ANY, _("Commands &Quick Reference"))
			self.Bind(wx.EVT_MENU, lambda evt: os.startfile(getDocFilePath("keyCommands.html")), item)
			item = menu_help.Append(wx.ID_ANY, _("What's &new"))
			self.Bind(wx.EVT_MENU, lambda evt: os.startfile(getDocFilePath("changes.html")), item)
			item = menu_help.Append(wx.ID_ANY, _("NVDA web site"))
			self.Bind(wx.EVT_MENU, lambda evt: os.startfile("http://www.nvda-project.org/"), item)
			item = menu_help.Append(wx.ID_ANY, _("License"))
			self.Bind(wx.EVT_MENU, lambda evt: os.startfile(getDocFilePath("copying.txt", False)), item)
			item = menu_help.Append(wx.ID_ANY, _("Contributors"))
			self.Bind(wx.EVT_MENU, lambda evt: os.startfile(getDocFilePath("contributors.txt", False)), item)
		item = menu_help.Append(wx.ID_ANY, _("We&lcome dialog"))
		self.Bind(wx.EVT_MENU, lambda evt: WelcomeDialog.run(), item)
		menu_help.AppendSeparator()
		if updateCheck:
			# Translators: The label of a menu item to manually check for an updated version of NVDA.
			item = menu_help.Append(wx.ID_ANY, _("Check for update..."))
			self.Bind(wx.EVT_MENU, frame.onCheckForUpdateCommand, item)
		item = menu_help.Append(wx.ID_ABOUT, _("About..."), _("About NVDA"))
		self.Bind(wx.EVT_MENU, frame.onAboutCommand, item)
		self.menu.AppendMenu(wx.ID_ANY,_("&Help"),menu_help)
		self.menu.AppendSeparator()
		item = self.menu.Append(wx.ID_ANY, _("&Revert to saved configuration"),_("Reset all settings to saved state"))
		self.Bind(wx.EVT_MENU, frame.onRevertToSavedConfigurationCommand, item)
		if not globalVars.appArgs.secure:
			item = self.menu.Append(wx.ID_ANY, _("&Reset configuration to factory defaults"),_("Reset all settings to default state"))
			self.Bind(wx.EVT_MENU, frame.onRevertToDefaultConfigurationCommand, item)
			item = self.menu.Append(wx.ID_SAVE, _("&Save configuration"), _("Write the current configuration to nvda.ini"))
			self.Bind(wx.EVT_MENU, frame.onSaveConfigurationCommand, item)
		if not globalVars.appArgs.secure:
			self.menu.AppendSeparator()
			item = self.menu.Append(wx.ID_ANY, _("Donate"))
			self.Bind(wx.EVT_MENU, lambda evt: os.startfile(DONATE_URL), item)
		self.menu.AppendSeparator()
		item = self.menu.Append(wx.ID_EXIT, _("E&xit"),_("Exit NVDA"))
		self.Bind(wx.EVT_MENU, frame.onExitCommand, item)

		self.Bind(wx.EVT_TASKBAR_RIGHT_DOWN, self.onActivate)

	def Destroy(self):
		self.menu.Destroy()
		super(SysTrayIcon, self).Destroy()

	def onActivate(self, evt):
		mainFrame.prePopup()
		self.PopupMenu(self.menu)
		mainFrame.postPopup()

def initialize():
	global mainFrame
	mainFrame = MainFrame()
	wx.GetApp().SetTopWindow(mainFrame)

def terminate():
	global mainFrame
	mainFrame.Destroy()

def showGui():
 	wx.CallAfter(mainFrame.showGui)

def quit():
	wx.CallAfter(mainFrame.onExitCommand, None)

def messageBox(message, caption=wx.MessageBoxCaptionStr, style=wx.OK | wx.CENTER, parent=None):
	"""Display a message dialog.
	This should be used for all message dialogs
	rather than using C{wx.MessageDialog} and C{wx.MessageBox} directly.
	@param message: The message text.
	@type message: str
	@param caption: The caption (title) of the dialog.
	@type caption: str
	@param style: Same as for wx.MessageBox.
	@type style: int
	@param parent: The parent window (optional).
	@type parent: C{wx.Window}
	@return: Same as for wx.MessageBox.
	@rtype: int
	"""
	global isInMessageBox
	wasAlready = isInMessageBox
	isInMessageBox = True
	if not parent:
		mainFrame.prePopup()
	res = wx.MessageBox(message, caption, style, parent or mainFrame)
	if not parent:
		mainFrame.postPopup()
	if not wasAlready:
		isInMessageBox = False
	return res

def runScriptModalDialog(dialog, callback=None):
	"""Run a modal dialog from a script.
	This will not block the caller,
	but will instead call C{callback} (if provided) with the result from the dialog.
	The dialog will be destroyed once the callback has returned.
	@param dialog: The dialog to show.
	@type dialog: C{wx.Dialog}
	@param callback: The optional callable to call with the result from the dialog.
	@type callback: callable
	"""
	def run():
		mainFrame.prePopup()
		res = dialog.ShowModal()
		mainFrame.postPopup()
		if callback:
			callback(res)
		dialog.Destroy()
	wx.CallAfter(run)

class WelcomeDialog(wx.Dialog):
	"""The NVDA welcome dialog.
	This provides essential information for new users, such as a description of the NVDA key and instructions on how to activate the NVDA menu.
	It also provides quick access to some important configuration options.
	This dialog is displayed the first time NVDA is started with a new configuration.
	"""

	WELCOME_MESSAGE = _(
		"Welcome to NVDA!\n"
		"Most commands for controlling NVDA require you to hold down the NVDA key while pressing other keys.\n"
		"By default, the numpad insert and main insert keys may both be used as the NVDA key.\n"
		"You can also configure NVDA to use the CapsLock as the NVDA key.\n"
		"Press NVDA+n at any time to activate the NVDA menu.\n"
		"From this menu, you can configure NVDA, get help and access other NVDA functions.\n"
	)

	def __init__(self, parent):
		super(WelcomeDialog, self).__init__(parent, wx.ID_ANY, _("Welcome to NVDA"))
		mainSizer=wx.BoxSizer(wx.VERTICAL)
		welcomeText = wx.StaticText(self, wx.ID_ANY, self.WELCOME_MESSAGE)
		mainSizer.Add(welcomeText,border=20,flag=wx.LEFT|wx.RIGHT|wx.TOP)
		optionsSizer = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, _("Options")), wx.HORIZONTAL)
		self.capsAsNVDAModifierCheckBox = wx.CheckBox(self, wx.ID_ANY, _("Use CapsLock as an NVDA modifier key"))
		self.capsAsNVDAModifierCheckBox.SetValue(config.conf["keyboard"]["useCapsLockAsNVDAModifierKey"])
		optionsSizer.Add(self.capsAsNVDAModifierCheckBox,flag=wx.TOP|wx.RIGHT,border=10)
		self.showWelcomeDialogAtStartupCheckBox = wx.CheckBox(self, wx.ID_ANY, _("Show this dialog when NVDA starts"))
		self.showWelcomeDialogAtStartupCheckBox.SetValue(config.conf["general"]["showWelcomeDialogAtStartup"])
		optionsSizer.Add(self.showWelcomeDialogAtStartupCheckBox,flag=wx.TOP|wx.LEFT,border=10)
		mainSizer.Add(optionsSizer,flag=wx.LEFT|wx.TOP|wx.RIGHT,border=20)
		mainSizer.Add(self.CreateButtonSizer(wx.OK),flag=wx.TOP|wx.BOTTOM|wx.ALIGN_CENTER_HORIZONTAL,border=20)
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)

		self.SetSizer(mainSizer)
		mainSizer.Fit(self)
		self.capsAsNVDAModifierCheckBox.SetFocus()

	def onOk(self, evt):
		config.conf["keyboard"]["useCapsLockAsNVDAModifierKey"] = self.capsAsNVDAModifierCheckBox.IsChecked()
		config.conf["general"]["showWelcomeDialogAtStartup"] = self.showWelcomeDialogAtStartupCheckBox.IsChecked()
		try:
			config.save()
		except:
			pass
		self.Close()

	@classmethod
	def run(cls):
		"""Prepare and display an instance of this dialog.
		This does not require the dialog to be instantiated.
		"""
		mainFrame.prePopup()
		d = cls(mainFrame)
		d.ShowModal()
		d.Destroy()
		mainFrame.postPopup()

class ConfigFileErrorDialog(wx.Dialog):
	"""A configuration file error dialog.
	This dialog tells the user that their configuration file is broken.
	"""

	MESSAGE=_("""Your configuration file contains errors. 
Press 'Ok' to fix these errors, or press 'Cancel' if you wish to manually edit your config file at a later stage to make corrections. More details about the errors can be found in the log file.
""")

	def __init__(self, parent):
		super(ConfigFileErrorDialog, self).__init__(parent, wx.ID_ANY, _("Configuration File Error"))
		mainSizer=wx.BoxSizer(wx.VERTICAL)
		messageText = wx.StaticText(self, wx.ID_ANY, self.MESSAGE)
		mainSizer.Add(messageText,border=20,flag=wx.LEFT|wx.RIGHT|wx.TOP)
		mainSizer.Add(self.CreateButtonSizer(wx.OK|wx.CANCEL),flag=wx.TOP|wx.BOTTOM|wx.ALIGN_CENTER_HORIZONTAL,border=20)
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		self.SetSizer(mainSizer)
		mainSizer.Fit(self)

	def onOk(self, evt):
		globalVars.configFileError=None
		config.save()
		self.Close()

	@classmethod
	def run(cls):
		"""Prepare and display an instance of this dialog.
		This does not require the dialog to be instantiated.
		"""
		mainFrame.prePopup()
		d = cls(mainFrame)
		d.ShowModal()
		d.Destroy()
		mainFrame.postPopup()

class LauncherDialog(wx.Dialog):
	"""The dialog that is displayed when NVDA is started from the launcher.
	This displays the license and allows the user to install or create a portable copy of NVDA.
	"""

	def __init__(self, parent):
		super(LauncherDialog, self).__init__(parent, title=versionInfo.name)
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		sizer = wx.StaticBoxSizer(wx.StaticBox(self, label=_("License Agreement")), wx.VERTICAL)
		ctrl = wx.TextCtrl(self, size=(500, 400), style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH)
		ctrl.Value = codecs.open(getDocFilePath("copying.txt", False), "r", encoding="UTF-8").read()
		sizer.Add(ctrl)
		ctrl = self.licenseAgreeCheckbox = wx.CheckBox(self, label=_("I &agree"))
		ctrl.Value = False
		sizer.Add(ctrl)
		ctrl.Bind(wx.EVT_CHECKBOX, self.onLicenseAgree)
		mainSizer.Add(sizer)

		sizer = wx.GridSizer(rows=2, cols=2)
		self.actionButtons = []
		ctrl = wx.Button(self, label=_("&Install NVDA on this computer"))
		sizer.Add(ctrl)
		ctrl.Bind(wx.EVT_BUTTON, lambda evt: self.onAction(evt, mainFrame.onInstallCommand))
		self.actionButtons.append(ctrl)
		ctrl = wx.Button(self, label=_("Create &portable copy"))
		sizer.Add(ctrl)
		ctrl.Bind(wx.EVT_BUTTON, lambda evt: self.onAction(evt, mainFrame.onCreatePortableCopyCommand))
		self.actionButtons.append(ctrl)
		ctrl = wx.Button(self, label=_("&Continue running"))
		sizer.Add(ctrl)
		ctrl.Bind(wx.EVT_BUTTON, self.onContinueRunning)
		self.actionButtons.append(ctrl)
		sizer.Add(wx.Button(self, label=_("E&xit"), id=wx.ID_CANCEL))
		# If we bind this on the button, it fails to trigger when the dialog is closed.
		self.Bind(wx.EVT_BUTTON, self.onExit, id=wx.ID_CANCEL)
		mainSizer.Add(sizer)
		for ctrl in self.actionButtons:
			ctrl.Disable()

		self.Sizer = mainSizer
		mainSizer.Fit(self)

	def onLicenseAgree(self, evt):
		for ctrl in self.actionButtons:
			ctrl.Enable(evt.IsChecked())

	def onAction(self, evt, func):
		self.Destroy()
		func(evt)

	def onContinueRunning(self, evt):
		self.Destroy()
		core.doStartupDialogs()

	def onExit(self, evt):
		wx.GetApp().ExitMainLoop()

	@classmethod
	def run(cls):
		"""Prepare and display an instance of this dialog.
		This does not require the dialog to be instantiated.
		"""
		mainFrame.prePopup()
		d = cls(mainFrame)
		d.Show()
		mainFrame.postPopup()

class ExecAndPump(threading.Thread):
	"""Executes the given function with given args and kwargs in a background thread while blocking and pumping in the current thread."""

	def __init__(self,func,*args,**kwargs):
		self.func=func
		self.args=args
		self.kwargs=kwargs
		super(ExecAndPump,self).__init__()
		self.threadExc=None
		self.start()
		time.sleep(0.1)
		threadHandle=ctypes.c_int()
		threadHandle.value=ctypes.windll.kernel32.OpenThread(0x100000,False,self.ident)
		msg=ctypes.wintypes.MSG()
		while ctypes.windll.user32.MsgWaitForMultipleObjects(1,ctypes.byref(threadHandle),False,-1,255)==1:
			while ctypes.windll.user32.PeekMessageW(ctypes.byref(msg),None,0,0,1):
				ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
				ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
		if self.threadExc:
			raise self.threadExc

	def run(self):
		try:
			self.func(*self.args,**self.kwargs)
		except Exception as e:
			self.threadExc=e
			log.debugWarning("task had errors",exc_info=True)

class IndeterminateProgressDialog(wx.ProgressDialog):

	def __init__(self, parent, title, message):
		super(IndeterminateProgressDialog, self).__init__(title, message, parent=parent)
		self._speechCounter = -1
		self.timer = wx.PyTimer(self.Pulse)
		self.timer.Start(1000)
		self.Raise()

	def Pulse(self):
		super(IndeterminateProgressDialog, self).Pulse()
		# We want progress to be spoken on the first pulse and every 10 pulses thereafter.
		# Therefore, cycle from 0 to 9 inclusive.
		self._speechCounter = (self._speechCounter + 1) % 10
		pbConf = config.conf["presentation"]["progressBarUpdates"]
		if pbConf["progressBarOutputMode"] == "off":
			return
		if not pbConf["reportBackgroundProgressBars"] and not self.IsActive():
			return
		if pbConf["progressBarOutputMode"] in ("beep", "both"):
			tones.beep(440, 40)
		if pbConf["progressBarOutputMode"] in ("speak", "both") and self._speechCounter == 0:
			# Translators: Announced periodically to indicate progress for an indeterminate progress bar.
			speech.speakMessage(_("Please wait"))

	def done(self):
		self.timer.Stop()
		if self.IsActive():
			tones.beep(1760, 40)
		self.Hide()
		self.Destroy()
