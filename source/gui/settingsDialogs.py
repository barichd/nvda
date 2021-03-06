#settingsDialogs.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2007 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import glob
import os
import copy
import wx
import winUser
import logHandler
import installer
from synthDriverHandler import *
import config
import languageHandler
import speech
import gui
import globalVars
from logHandler import log
import nvwave
import speechDictHandler
import appModuleHandler
import queueHandler
import braille
import core
import keyboardHandler
import characterProcessing
try:
	import updateCheck
except RuntimeError:
	updateCheck = None

class SettingsDialog(wx.Dialog):
	"""A settings dialog.
	A settings dialog consists of one or more settings controls and OK and Cancel buttons.
	Action may be taken in response to the OK or Cancel buttons.

	To use this dialog:
		* Set L{title} to the title of the dialog.
		* Override L{makeSettings} to populate a given sizer with the settings controls.
		* Optionally, override L{postInit} to perform actions after the dialog is created, such as setting the focus.
		* Optionally, extend one or both of L{onOk} or L{onCancel} to perform actions in response to the OK or Cancel buttons, respectively.

	@ivar title: The title of the dialog.
	@type title: str
	"""

	class MultiInstanceError(RuntimeError): pass

	_hasInstance=False

	title = ""

	def __new__(cls, *args, **kwargs):
		if SettingsDialog._hasInstance:
			raise SettingsDialog.MultiInstanceError("Only one instance of SettingsDialog can exist at a time")
		obj = super(SettingsDialog, cls).__new__(cls, *args, **kwargs)
		SettingsDialog._hasInstance=True
		return obj

	def __init__(self, parent):
		"""
		@param parent: The parent for this dialog; C{None} for no parent.
		@type parent: wx.Window
		"""
		super(SettingsDialog, self).__init__(parent, wx.ID_ANY, self.title)
		mainSizer=wx.BoxSizer(wx.VERTICAL)
		self.settingsSizer=wx.BoxSizer(wx.VERTICAL)
		self.makeSettings(self.settingsSizer)
		mainSizer.Add(self.settingsSizer,border=20,flag=wx.LEFT|wx.RIGHT|wx.TOP)
		buttonSizer=self.CreateButtonSizer(wx.OK|wx.CANCEL)
		mainSizer.Add(buttonSizer,border=20,flag=wx.LEFT|wx.RIGHT|wx.BOTTOM)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.Bind(wx.EVT_BUTTON,self.onOk,id=wx.ID_OK)
		self.Bind(wx.EVT_BUTTON,self.onCancel,id=wx.ID_CANCEL)
		self.postInit()

	def __del__(self):
		SettingsDialog._hasInstance=False

	def makeSettings(self, sizer):
		"""Populate the dialog with settings controls.
		Subclasses must override this method.
		@param sizer: The sizer to which to add the settings controls.
		@type sizer: wx.Sizer
		"""
		raise NotImplementedError

	def postInit(self):
		"""Called after the dialog has been created.
		For example, this might be used to set focus to the desired control.
		Sub-classes may override this method.
		"""

	def onOk(self, evt):
		"""Take action in response to the OK button being pressed.
		Sub-classes may extend this method.
		This base method should always be called to clean up the dialog.
		"""
		self.Destroy()

	def onCancel(self, evt):
		"""Take action in response to the Cancel button being pressed.
		Sub-classes may extend this method.
		This base method should always be called to clean up the dialog.
		"""
		self.Destroy()

class GeneralSettingsDialog(SettingsDialog):
	# Translators: This is the label for the general settings dialog.
	title = _("General Settings")
	LOG_LEVELS = (
		(log.INFO, _("info")),
		(log.DEBUGWARNING, _("debug warning")),
		(log.IO, _("input/output")),
		(log.DEBUG, _("debug"))
	)

	def makeSettings(self, settingsSizer):
		languageSizer=wx.BoxSizer(wx.HORIZONTAL)
		languageLabel=wx.StaticText(self,-1,label=_("&Language (requires restart to fully take effect):"))
		languageSizer.Add(languageLabel)
		languageListID=wx.NewId()
		self.languageNames=languageHandler.getAvailableLanguages()
		self.languageList=wx.Choice(self,languageListID,name=_("Language"),choices=[x[1] for x in self.languageNames])
		self.languageList.SetToolTip(wx.ToolTip("Choose the language NVDA's messages and user interface should be presented in."))
		try:
			self.oldLanguage=config.conf["general"]["language"]
			index=[x[0] for x in self.languageNames].index(self.oldLanguage)
			self.languageList.SetSelection(index)
		except:
			pass
		languageSizer.Add(self.languageList)
		if globalVars.appArgs.secure:
			self.languageList.Disable()
		settingsSizer.Add(languageSizer,border=10,flag=wx.BOTTOM)
		self.saveOnExitCheckBox=wx.CheckBox(self,wx.NewId(),label=_("&Save configuration on exit"))
		self.saveOnExitCheckBox.SetValue(config.conf["general"]["saveConfigurationOnExit"])
		if globalVars.appArgs.secure:
			self.saveOnExitCheckBox.Disable()
		settingsSizer.Add(self.saveOnExitCheckBox,border=10,flag=wx.BOTTOM)
		self.askToExitCheckBox=wx.CheckBox(self,wx.NewId(),label=_("&Warn before exiting NVDA"))
		self.askToExitCheckBox.SetValue(config.conf["general"]["askToExit"])
		settingsSizer.Add(self.askToExitCheckBox,border=10,flag=wx.BOTTOM)
		logLevelSizer=wx.BoxSizer(wx.HORIZONTAL)
		logLevelLabel=wx.StaticText(self,-1,label=_("L&ogging level:"))
		logLevelSizer.Add(logLevelLabel)
		logLevelListID=wx.NewId()
		self.logLevelList=wx.Choice(self,logLevelListID,name=_("Log level"),choices=[name for level, name in self.LOG_LEVELS])
		curLevel = log.getEffectiveLevel()
		for index, (level, name) in enumerate(self.LOG_LEVELS):
			if level == curLevel:
				self.logLevelList.SetSelection(index)
				break
		else:
			log.debugWarning("Could not set log level list to current log level") 
		logLevelSizer.Add(self.logLevelList)
		settingsSizer.Add(logLevelSizer,border=10,flag=wx.BOTTOM)
		self.startAfterLogonCheckBox = wx.CheckBox(self, wx.ID_ANY, label=_("&Automatically start NVDA after I log on to Windows"))
		self.startAfterLogonCheckBox.SetValue(config.getStartAfterLogon())
		if globalVars.appArgs.secure or not config.isInstalledCopy():
			self.startAfterLogonCheckBox.Disable()
		settingsSizer.Add(self.startAfterLogonCheckBox)
		self.startOnLogonScreenCheckBox = wx.CheckBox(self, wx.ID_ANY, label=_("Use NVDA on the Windows logon screen (requires administrator privileges)"))
		self.startOnLogonScreenCheckBox.SetValue(config.getStartOnLogonScreen())
		if globalVars.appArgs.secure or not config.isServiceInstalled():
			self.startOnLogonScreenCheckBox.Disable()
		settingsSizer.Add(self.startOnLogonScreenCheckBox)
		self.copySettingsButton= wx.Button(self, wx.ID_ANY, label=_("Use currently saved settings on the logon and other secure screens (requires administrator privileges)"))
		self.copySettingsButton.Bind(wx.EVT_BUTTON,self.onCopySettings)
		if globalVars.appArgs.secure or not config.isServiceInstalled():
			self.copySettingsButton.Disable()
		settingsSizer.Add(self.copySettingsButton)
		if updateCheck:
			# Translators: The label of a checkbox to toggle automatic checking for updated versions of NVDA.
			item=self.autoCheckForUpdatesCheckBox=wx.CheckBox(self,label=_("Automatically check for &updates to NVDA"))
			item.Value=config.conf["update"]["autoCheck"]
			if globalVars.appArgs.secure:
				item.Disable()
			settingsSizer.Add(item)

	def postInit(self):
		self.languageList.SetFocus()

	def onCopySettings(self,evt):
		for packageType in ('addons','appModules','globalPlugins','brailleDisplayDrivers','synthDrivers'):
			if len(os.listdir(os.path.join(globalVars.appArgs.configPath,packageType)))>0:
				if gui.messageBox(
					_("Custom plugins were detected in your user settings directory. Copying these to the system profile could be a security risk. Do you still wish to copy your settings?"),
					_("Warning"),wx.YES|wx.NO|wx.ICON_WARNING,self
				)==wx.NO:
					return
				break
		progressDialog = gui.IndeterminateProgressDialog(gui.mainFrame,
		# Translators: The title of the dialog presented while settings are being copied 
		_("Copying Settings"),
		# Translators: The message displayed while settings are being copied to the system configuration (for use on Windows logon etc) 
		_("Please wait while settings are copied to the system configuration."))
		while True:
			try:
				gui.ExecAndPump(config.setSystemConfigToCurrentConfig)
				res=True
				break
			except installer.RetriableFailure:
				log.debugWarning("Error when copying settings to system config",exc_info=True)
				# Translators: a message dialog asking to retry or cancel when copying settings  fails
				message=_("Unable to copy a file. Perhaps it is currently being used by another process or you have run out of disc space on the drive you are copying to.")
				# Translators: the title of a retry cancel dialog when copying settings  fails
				title=_("Error Copying")
				if winUser.MessageBox(None,message,title,winUser.MB_RETRYCANCEL)==winUser.IDRETRY:
					continue
				res=False
				break
			except:
				log.debugWarning("Error when copying settings to system config",exc_info=True)
				res=False
				break
		progressDialog.done()
		del progressDialog
		if not res:
			gui.messageBox(_("Error copying NVDA user settings"),_("Error"),wx.OK|wx.ICON_ERROR,self)
		else:
			gui.messageBox(_("Successfully copied NVDA user settings"),_("Success"),wx.OK|wx.ICON_INFORMATION,self)

	def onOk(self,evt):
		newLanguage=[x[0] for x in self.languageNames][self.languageList.GetSelection()]
		if newLanguage!=self.oldLanguage:
			try:
				languageHandler.setLanguage(newLanguage)
			except:
				log.error("languageHandler.setLanguage", exc_info=True)
				gui.messageBox(_("Error in %s language file")%newLanguage,_("Language Error"),wx.OK|wx.ICON_WARNING,self)
				return
		config.conf["general"]["language"]=newLanguage
		config.conf["general"]["saveConfigurationOnExit"]=self.saveOnExitCheckBox.IsChecked()
		config.conf["general"]["askToExit"]=self.askToExitCheckBox.IsChecked()
		logLevel=self.LOG_LEVELS[self.logLevelList.GetSelection()][0]
		config.conf["general"]["loggingLevel"]=logHandler.levelNames[logLevel]
		logHandler.setLogLevelFromConfig()
		if self.startAfterLogonCheckBox.IsEnabled():
			config.setStartAfterLogon(self.startAfterLogonCheckBox.GetValue())
		if self.startOnLogonScreenCheckBox.IsEnabled():
			try:
				config.setStartOnLogonScreen(self.startOnLogonScreenCheckBox.GetValue())
			except (WindowsError, RuntimeError):
				gui.messageBox(_("This change requires administrator privileges."), _("Insufficient Privileges"), style=wx.OK | wx.ICON_ERROR, parent=self)
		if updateCheck:
			config.conf["update"]["autoCheck"]=self.autoCheckForUpdatesCheckBox.IsChecked()
			updateCheck.terminate()
			updateCheck.initialize()
		if self.oldLanguage!=newLanguage:
			if gui.messageBox(
				_("For the new language to take effect, the configuration must be saved and NVDA must be restarted. Press enter to save and restart NVDA, or cancel to manually save and exit at a later time."),
				_("Language Configuration Change"),wx.OK|wx.CANCEL|wx.ICON_WARNING,self
			)==wx.OK:
				config.save()
				queueHandler.queueFunction(queueHandler.eventQueue,core.restart)
		super(GeneralSettingsDialog, self).onOk(evt)

class SynthesizerDialog(SettingsDialog):
	# Translators: This is the label for the synthesizer dialog.
	title = _("Synthesizer")

	def makeSettings(self, settingsSizer):
		synthListSizer=wx.BoxSizer(wx.HORIZONTAL)
		# Translators: This is a label for the select
		# synthesizer combobox in the synthesizer dialog.
		synthListLabel=wx.StaticText(self,-1,label=_("&Synthesizer:"))
		synthListID=wx.NewId()
		driverList=getSynthList()
		self.synthNames=[x[0] for x in driverList]
		options=[x[1] for x in driverList]
		self.synthList=wx.Choice(self,synthListID,choices=options)
		try:
			index=self.synthNames.index(getSynth().name)
			self.synthList.SetSelection(index)
		except:
			pass
		synthListSizer.Add(synthListLabel)
		synthListSizer.Add(self.synthList)
		settingsSizer.Add(synthListSizer,border=10,flag=wx.BOTTOM)
		deviceListSizer=wx.BoxSizer(wx.HORIZONTAL)
		# Translators: This is the label for the select output
		# device combo in the synthesizer dialog. Examples of
		# of an output device are default soundcard, usb
		# headphones, etc.
		deviceListLabel=wx.StaticText(self,-1,label=_("Output &device:"))
		deviceListID=wx.NewId()
		deviceNames=nvwave.getOutputDeviceNames()
		self.deviceList=wx.Choice(self,deviceListID,choices=deviceNames)
		try:
			selection = deviceNames.index(config.conf["speech"]["outputDevice"])
		except ValueError:
			selection = 0
		self.deviceList.SetSelection(selection)
		deviceListSizer.Add(deviceListLabel)
		deviceListSizer.Add(self.deviceList)
		settingsSizer.Add(deviceListSizer,border=10,flag=wx.BOTTOM)

	def postInit(self):
		self.synthList.SetFocus()

	def onOk(self,evt):
		config.conf["speech"]["outputDevice"]=self.deviceList.GetStringSelection()
		newSynth=self.synthNames[self.synthList.GetSelection()]
		if not setSynth(newSynth):
			# Translators: This message is presented when
			# NVDA is unable to load the selected
			# synthesizer.
			gui.messageBox(_("Could not load the %s synthesizer.")%newSynth,_("Synthesizer Error"),wx.OK|wx.ICON_WARNING,self)
			return 
		super(SynthesizerDialog, self).onOk(evt)

class SynthSettingChanger(object):
	"""Functor which acts as calback for GUI events."""

	def __init__(self,setting):
		self.setting=setting

	def __call__(self,evt):
		val=evt.GetSelection()
		setattr(getSynth(),self.setting.name,val)

class StringSynthSettingChanger(SynthSettingChanger):
	"""Same as L{SynthSettingChanger} but handles combobox events."""
	def __init__(self,setting,dialog):
		self.dialog=dialog
		super(StringSynthSettingChanger,self).__init__(setting)

	def __call__(self,evt):
		if self.setting.name=="voice":
			# Cancel speech first so that the voice will change immediately instead of the change being queued.
			speech.cancelSpeech()
			changeVoice(getSynth(),getattr(self.dialog,"_%ss"%self.setting.name)[evt.GetSelection()].ID)
			self.dialog.updateVoiceSettings(changedSetting=self.setting.name)
		else:
			setattr(getSynth(),self.setting.name,getattr(self.dialog,"_%ss"%self.setting.name)[evt.GetSelection()].ID)

class VoiceSettingsSlider(wx.Slider):

	def __init__(self,*args, **kwargs):
		super(VoiceSettingsSlider,self).__init__(*args,**kwargs)
		self.Bind(wx.EVT_CHAR, self.onSliderChar)

	def SetValue(self,i):
		super(VoiceSettingsSlider, self).SetValue(i)
		evt = wx.CommandEvent(wx.wxEVT_COMMAND_SLIDER_UPDATED,self.GetId())
		evt.SetInt(i)
		self.ProcessEvent(evt)
		# HACK: Win events don't seem to be sent for certain explicitly set values,
		# so send our own win event.
		# This will cause duplicates in some cases, but NVDA will filter them out.
		winUser.user32.NotifyWinEvent(winUser.EVENT_OBJECT_VALUECHANGE,self.Handle,winUser.OBJID_CLIENT,winUser.CHILDID_SELF)

	def onSliderChar(self, evt):
		key = evt.KeyCode
		if key == wx.WXK_UP:
			newValue = min(self.Value + self.LineSize, self.Max)
		elif key == wx.WXK_DOWN:
			newValue = max(self.Value - self.LineSize, self.Min)
		elif key == wx.WXK_PRIOR:
			newValue = min(self.Value + self.PageSize, self.Max)
		elif key == wx.WXK_NEXT:
			newValue = max(self.Value - self.PageSize, self.Min)
		elif key == wx.WXK_HOME:
			newValue = self.Max
		elif key == wx.WXK_END:
			newValue = self.Min
		else:
			evt.Skip()
			return
		self.SetValue(newValue)

class VoiceSettingsDialog(SettingsDialog):
	# Translators: This is the label for the voice settings dialog.
	title = _("Voice Settings")

	@classmethod
	def _setSliderStepSizes(cls, slider, setting):
		slider.SetLineSize(setting.minStep)
		slider.SetPageSize(setting.largeStep)

	def makeSettingControl(self,setting):
		"""Constructs appropriate GUI controls for given L{SynthSetting} such as label and slider.
		@param setting: Setting to construct controls for
		@type setting: L{SynthSetting}
		@returns: WXSizer containing newly created controls.
		@rtype: L{wx.BoxSizer}
		"""
		sizer=wx.BoxSizer(wx.HORIZONTAL)
		label=wx.StaticText(self,wx.ID_ANY,label="%s:"%setting.i18nName)
		slider=VoiceSettingsSlider(self,wx.ID_ANY,minValue=0,maxValue=100,name="%s:"%setting.i18nName)
		setattr(self,"%sSlider"%setting.name,slider)
		slider.Bind(wx.EVT_SLIDER,SynthSettingChanger(setting))
		self._setSliderStepSizes(slider,setting)
		slider.SetValue(getattr(getSynth(),setting.name))
		sizer.Add(label)
		sizer.Add(slider)
		if self.lastControl:
			slider.MoveAfterInTabOrder(self.lastControl)
		self.lastControl=slider
		return sizer

	def makeStringSettingControl(self,setting):
		"""Same as L{makeSettingControl} but for string settings. Returns sizer with label and combobox."""
		sizer=wx.BoxSizer(wx.HORIZONTAL)
		label=wx.StaticText(self,wx.ID_ANY,label="%s:"%setting.i18nName)
		synth=getSynth()
		setattr(self,"_%ss"%setting.name,getattr(synth,"available%ss"%setting.name.capitalize()).values())
		l=getattr(self,"_%ss"%setting.name)###
		lCombo=wx.Choice(self,wx.ID_ANY,name="%s:"%setting.i18nName,choices=[x.name for x in l])
		setattr(self,"%sList"%setting.name,lCombo)
		try:
			cur=getattr(synth,setting.name)
			i=[x.ID for x in l].index(cur)
			lCombo.SetSelection(i)
		except ValueError:
			pass
		lCombo.Bind(wx.EVT_CHOICE,StringSynthSettingChanger(setting,self))
		sizer.Add(label)
		sizer.Add(lCombo)
		if self.lastControl:
			lCombo.MoveAfterInTabOrder(self.lastControl)
		self.lastControl=lCombo
		return sizer

	def makeBooleanSettingControl(self,setting):
		"""Same as L{makeSettingControl} but for boolean settings. Returns checkbox."""
		checkbox=wx.CheckBox(self,wx.ID_ANY,label=setting.i18nName)
		setattr(self,"%sCheckbox"%setting.name,checkbox)
		checkbox.Bind(wx.EVT_CHECKBOX,
			lambda evt: setattr(getSynth(),setting.name,evt.IsChecked()))
		checkbox.SetValue(getattr(getSynth(),setting.name))
		if self.lastControl:
			checkbox.MoveAfterInTabOrder(self.lastControl)
		self.lastControl=checkbox
		return checkbox

	def makeSettings(self, settingsSizer):
		self.sizerDict={}
		self.lastControl=None
		#Create controls for Synth Settings
		self.updateVoiceSettings()
		# Translators: This is the label for a checkbox in the
		# voice settings dialog.
		self.autoLanguageSwitchingCheckbox=wx.CheckBox(self,wx.NewId(),label=_("Automatic language switching (when supported)"))
		self.autoLanguageSwitchingCheckbox.SetValue(config.conf["speech"]["autoLanguageSwitching"])
		settingsSizer.Add(self.autoLanguageSwitchingCheckbox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# voice settings dialog.
		self.autoDialectSwitchingCheckbox=wx.CheckBox(self,wx.NewId(),label=_("Automatic dialect switching (when supported)"))
		self.autoDialectSwitchingCheckbox.SetValue(config.conf["speech"]["autoDialectSwitching"])
		settingsSizer.Add(self.autoDialectSwitchingCheckbox,border=10,flag=wx.BOTTOM)
		sizer=wx.BoxSizer(wx.HORIZONTAL)
		# Translators: This is the label for a combobox in the
		# voice settings dialog.
		sizer.Add(wx.StaticText(self,wx.ID_ANY,label=_("Punctuation/symbol &level:")))
		symbolLevelLabels=characterProcessing.SPEECH_SYMBOL_LEVEL_LABELS
		self.symbolLevelList=wx.Choice(self,wx.ID_ANY,choices=[symbolLevelLabels[level] for level in characterProcessing.CONFIGURABLE_SPEECH_SYMBOL_LEVELS])
		curLevel = config.conf["speech"]["symbolLevel"]
		self.symbolLevelList.SetSelection(characterProcessing.CONFIGURABLE_SPEECH_SYMBOL_LEVELS.index(curLevel))
		sizer.Add(self.symbolLevelList)
		settingsSizer.Add(sizer,border=10,flag=wx.BOTTOM)
		capPitchChangeLabel=wx.StaticText(self,-1,label=_("Capital pitch change percentage"))
		settingsSizer.Add(capPitchChangeLabel)
		self.capPitchChangeEdit=wx.TextCtrl(self,wx.NewId())
		self.capPitchChangeEdit.SetValue(str(config.conf["speech"][getSynth().name]["capPitchChange"]))
		settingsSizer.Add(self.capPitchChangeEdit,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# voice settings dialog.
		self.sayCapForCapsCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Say &cap before capitals"))
		self.sayCapForCapsCheckBox.SetValue(config.conf["speech"][getSynth().name]["sayCapForCapitals"])
		settingsSizer.Add(self.sayCapForCapsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# voice settings dialog.
		self.beepForCapsCheckBox = wx.CheckBox(self, wx.NewId(), label = _("&Beep for capitals"))
		self.beepForCapsCheckBox.SetValue(config.conf["speech"][getSynth().name]["beepForCapitals"])
		settingsSizer.Add(self.beepForCapsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# voice settings dialog.
		self.useSpellingFunctionalityCheckBox = wx.CheckBox(self, wx.NewId(), label = _("Use &spelling functionality if supported"))
		self.useSpellingFunctionalityCheckBox.SetValue(config.conf["speech"][getSynth().name]["useSpellingFunctionality"])
		settingsSizer.Add(self.useSpellingFunctionalityCheckBox,border=10,flag=wx.BOTTOM)

	def postInit(self):
		try:
			setting=getSynth().supportedSettings[0]
			control=getattr(self,"%sSlider"%setting.name) if isinstance(setting,NumericSynthSetting) else getattr(self,"%sList"%setting.name)
			control.SetFocus()
		except IndexError:
			self.symbolLevelList.SetFocus()

	def updateVoiceSettings(self, changedSetting=None):
		"""Creates, hides or updates existing GUI controls for all of supported settings."""
		synth=getSynth()
		#firstly check already created options
		for name,sizer in self.sizerDict.iteritems():
			if name == changedSetting:
				# Changing a setting shouldn't cause that setting itself to disappear.
				continue
			if not synth.isSupported(name):
				self.settingsSizer.Hide(sizer)
		#Create new controls, update already existing
		for setting in synth.supportedSettings:
			if setting.name == changedSetting:
				# Changing a setting shouldn't cause that setting's own values to change.
				continue
			if setting.name in self.sizerDict: #update a value
				self.settingsSizer.Show(self.sizerDict[setting.name])
				if isinstance(setting,NumericSynthSetting):
					getattr(self,"%sSlider"%setting.name).SetValue(getattr(synth,setting.name))
				elif isinstance(setting,BooleanSynthSetting):
					getattr(self,"%sCheckbox"%setting.name).SetValue(getattr(synth,setting.name))
				else:
					l=getattr(self,"_%ss"%setting.name)
					lCombo=getattr(self,"%sList"%setting.name)
					try:
						cur=getattr(synth,setting.name)
						i=[x.ID for x in l].index(cur)
						lCombo.SetSelection(i)
					except ValueError:
						pass
			else: #create a new control
				if isinstance(setting,NumericSynthSetting):
					settingMaker=self.makeSettingControl
				elif isinstance(setting,BooleanSynthSetting):
					settingMaker=self.makeBooleanSettingControl
				else:
					settingMaker=self.makeStringSettingControl
				s=settingMaker(setting)
				self.sizerDict[setting.name]=s
				self.settingsSizer.Insert(len(self.sizerDict)-1,s,border=10,flag=wx.BOTTOM)
		#Update graphical layout of the dialog
		self.settingsSizer.Layout()

	def onCancel(self,evt):
		#unbind change events for string settings as wx closes combo boxes on cancel
		for setting in getSynth().supportedSettings:
			if isinstance(setting,(NumericSynthSetting,BooleanSynthSetting)): continue
			getattr(self,"%sList"%setting.name).Unbind(wx.EVT_CHOICE)
		#restore settings
		getSynth().loadSettings()
		super(VoiceSettingsDialog, self).onCancel(evt)

	def onOk(self,evt):
		getSynth().saveSettings()
		config.conf["speech"]["autoLanguageSwitching"]=self.autoLanguageSwitchingCheckbox.IsChecked()
		config.conf["speech"]["autoDialectSwitching"]=self.autoDialectSwitchingCheckbox.IsChecked()
		config.conf["speech"]["symbolLevel"]=characterProcessing.CONFIGURABLE_SPEECH_SYMBOL_LEVELS[self.symbolLevelList.GetSelection()]
		capPitchChange=self.capPitchChangeEdit.Value
		try:
			capPitchChange=int(capPitchChange)
		except ValueError:
			capPitchChange=0
		config.conf["speech"][getSynth().name]["capPitchChange"]=min(max(capPitchChange,-100),100)
		config.conf["speech"][getSynth().name]["sayCapForCapitals"]=self.sayCapForCapsCheckBox.IsChecked()
		config.conf["speech"][getSynth().name]["beepForCapitals"]=self.beepForCapsCheckBox.IsChecked()
		config.conf["speech"][getSynth().name]["useSpellingFunctionality"]=self.useSpellingFunctionalityCheckBox.IsChecked()
		super(VoiceSettingsDialog, self).onOk(evt)

class KeyboardSettingsDialog(SettingsDialog):
	# Translators: This is the label for the keyboard settings dialog.
	title = _("Keyboard Settings")

	def makeSettings(self, settingsSizer):
		kbdSizer=wx.BoxSizer(wx.HORIZONTAL)
		# Translators: This is the label for a combobox in the
		# keyboard settings dialog.
		kbdLabel=wx.StaticText(self,-1,label=_("&Keyboard layout:"))
		kbdSizer.Add(kbdLabel)
		kbdListID=wx.NewId()
		layouts=keyboardHandler.KeyboardInputGesture.LAYOUTS
		self.kbdNames=sorted(layouts)
		# Translators: This is the name of a combobox in the keyboard settings dialog.
		self.kbdList=wx.Choice(self,kbdListID,name=_("Keyboard layout"),choices=[layouts[layout] for layout in self.kbdNames])
		try:
			index=self.kbdNames.index(config.conf['keyboard']['keyboardLayout'])
			self.kbdList.SetSelection(index)
		except:
			log.debugWarning("Could not set Keyboard layout list to current layout",exc_info=True) 
		kbdSizer.Add(self.kbdList)
		settingsSizer.Add(kbdSizer,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# keyboard settings dialog.
		self.capsAsNVDAModifierCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Use CapsLock as an NVDA modifier key"))
		self.capsAsNVDAModifierCheckBox.SetValue(config.conf["keyboard"]["useCapsLockAsNVDAModifierKey"])
		settingsSizer.Add(self.capsAsNVDAModifierCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# keyboard settings dialog.
		self.numpadInsertAsNVDAModifierCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Use numpad Insert as an NVDA modifier key"))
		self.numpadInsertAsNVDAModifierCheckBox.SetValue(config.conf["keyboard"]["useNumpadInsertAsNVDAModifierKey"])
		settingsSizer.Add(self.numpadInsertAsNVDAModifierCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# keyboard settings dialog.
		self.extendedInsertAsNVDAModifierCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Use extended Insert as an NVDA modifier key"))
		self.extendedInsertAsNVDAModifierCheckBox.SetValue(config.conf["keyboard"]["useExtendedInsertAsNVDAModifierKey"])
		settingsSizer.Add(self.extendedInsertAsNVDAModifierCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# keyboard settings dialog.
		self.charsCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Speak typed &characters"))
		self.charsCheckBox.SetValue(config.conf["keyboard"]["speakTypedCharacters"])
		settingsSizer.Add(self.charsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# keyboard settings dialog.
		self.wordsCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Speak typed &words"))
		self.wordsCheckBox.SetValue(config.conf["keyboard"]["speakTypedWords"])
		settingsSizer.Add(self.wordsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# keyboard settings dialog.
		self.speechInterruptForCharsCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Speech interrupt for typed characters"))
		self.speechInterruptForCharsCheckBox.SetValue(config.conf["keyboard"]["speechInterruptForCharacters"])
		settingsSizer.Add(self.speechInterruptForCharsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# keyboard settings dialog.
		self.speechInterruptForEnterCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Speech interrupt for Enter key"))
		self.speechInterruptForEnterCheckBox.SetValue(config.conf["keyboard"]["speechInterruptForEnter"])
		settingsSizer.Add(self.speechInterruptForEnterCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# keyboard settings dialog.
		self.beepLowercaseCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Beep if typing lowercase letters when caps lock is on"))
		self.beepLowercaseCheckBox.SetValue(config.conf["keyboard"]["beepForLowercaseWithCapslock"])
		settingsSizer.Add(self.beepLowercaseCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# keyboard settings dialog.
		self.commandKeysCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Speak command &keys"))
		self.commandKeysCheckBox.SetValue(config.conf["keyboard"]["speakCommandKeys"])
		settingsSizer.Add(self.commandKeysCheckBox,border=10,flag=wx.BOTTOM)

	def postInit(self):
		self.kbdList.SetFocus()

	def onOk(self,evt):
		layout=self.kbdNames[self.kbdList.GetSelection()]
		config.conf['keyboard']['keyboardLayout']=layout
		config.conf["keyboard"]["useCapsLockAsNVDAModifierKey"]=self.capsAsNVDAModifierCheckBox.IsChecked()
		config.conf["keyboard"]["useNumpadInsertAsNVDAModifierKey"]=self.numpadInsertAsNVDAModifierCheckBox.IsChecked()
		config.conf["keyboard"]["useExtendedInsertAsNVDAModifierKey"]=self.extendedInsertAsNVDAModifierCheckBox.IsChecked()
		config.conf["keyboard"]["speakTypedCharacters"]=self.charsCheckBox.IsChecked()
		config.conf["keyboard"]["speakTypedWords"]=self.wordsCheckBox.IsChecked()
		config.conf["keyboard"]["speechInterruptForCharacters"]=self.speechInterruptForCharsCheckBox.IsChecked()
		config.conf["keyboard"]["speechInterruptForEnter"]=self.speechInterruptForEnterCheckBox.IsChecked()
		config.conf["keyboard"]["beepForLowercaseWithCapslock"]=self.beepLowercaseCheckBox.IsChecked()
		config.conf["keyboard"]["speakCommandKeys"]=self.commandKeysCheckBox.IsChecked()
		super(KeyboardSettingsDialog, self).onOk(evt)

class MouseSettingsDialog(SettingsDialog):
	# Translators: This is the label for the mouse settings dialog.
	title = _("Mouse Settings")

	def makeSettings(self, settingsSizer):
		# Translators: This is the label for a checkbox in the
		# mouse settings dialog.
		self.shapeCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report mouse &shape changes"))
		self.shapeCheckBox.SetValue(config.conf["mouse"]["reportMouseShapeChanges"])
		settingsSizer.Add(self.shapeCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# mouse settings dialog.
		self.mouseTrackingCheckBox=wx.CheckBox(self,wx.ID_ANY,label=_("Enable mouse &tracking"))
		self.mouseTrackingCheckBox.SetValue(config.conf["mouse"]["enableMouseTracking"])
		settingsSizer.Add(self.mouseTrackingCheckBox,border=10,flag=wx.BOTTOM)
		textUnitSizer=wx.BoxSizer(wx.HORIZONTAL)
		# Translators: This is the label for a combobox in the
		# mouse settings dialog.
		textUnitLabel=wx.StaticText(self,-1,label=_("Text &unit resolution:"))
		textUnitSizer.Add(textUnitLabel)
		import textInfos
		self.textUnits=[textInfos.UNIT_CHARACTER,textInfos.UNIT_WORD,textInfos.UNIT_LINE,textInfos.UNIT_PARAGRAPH]
		# Translators: This is the name of a combobox in the mouse settings dialog.
		self.textUnitComboBox=wx.Choice(self,wx.ID_ANY,name=_("text reporting unit"),choices=[textInfos.unitLabels[x] for x in self.textUnits])
		try:
			index=self.textUnits.index(config.conf["mouse"]["mouseTextUnit"])
		except:
			index=0
		self.textUnitComboBox.SetSelection(index)
		textUnitSizer.Add(self.textUnitComboBox)
		settingsSizer.Add(textUnitSizer,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# mouse settings dialog.
		self.reportObjectRoleCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report &role when mouse enters object"))
		self.reportObjectRoleCheckBox.SetValue(config.conf["mouse"]["reportObjectRoleOnMouseEnter"])
		settingsSizer.Add(self.reportObjectRoleCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# mouse settings dialog.
		self.audioCheckBox=wx.CheckBox(self,wx.NewId(),label=_("play audio coordinates when mouse moves"))
		self.audioCheckBox.SetValue(config.conf["mouse"]["audioCoordinatesOnMouseMove"])
		settingsSizer.Add(self.audioCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# mouse settings dialog.
		self.audioDetectBrightnessCheckBox=wx.CheckBox(self,wx.NewId(),label=_("brightness controls audio coordinates volume"))
		self.audioDetectBrightnessCheckBox.SetValue(config.conf["mouse"]["audioCoordinates_detectBrightness"])
		settingsSizer.Add(self.audioDetectBrightnessCheckBox,border=10,flag=wx.BOTTOM)

	def postInit(self):
		self.shapeCheckBox.SetFocus()

	def onOk(self,evt):
		config.conf["mouse"]["reportMouseShapeChanges"]=self.shapeCheckBox.IsChecked()
		config.conf["mouse"]["enableMouseTracking"]=self.mouseTrackingCheckBox.IsChecked()
		config.conf["mouse"]["mouseTextUnit"]=self.textUnits[self.textUnitComboBox.GetSelection()]
		config.conf["mouse"]["reportObjectRoleOnMouseEnter"]=self.reportObjectRoleCheckBox.IsChecked()
		config.conf["mouse"]["audioCoordinatesOnMouseMove"]=self.audioCheckBox.IsChecked()
		config.conf["mouse"]["audioCoordinates_detectBrightness"]=self.audioDetectBrightnessCheckBox.IsChecked()

		super(MouseSettingsDialog, self).onOk(evt)

class ReviewCursorDialog(SettingsDialog):
	# Translators: This is the label for the review cursor settings dialog.
	title = _("Review Cursor Settings")

	def makeSettings(self, settingsSizer):
		# Translators: This is the label for a checkbox in the
		# review cursor settings dialog.
		self.followFocusCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Follow system &focus"))
		self.followFocusCheckBox.SetValue(config.conf["reviewCursor"]["followFocus"])
		settingsSizer.Add(self.followFocusCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# review cursor settings dialog.
		self.followCaretCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Follow System &Caret"))
		self.followCaretCheckBox.SetValue(config.conf["reviewCursor"]["followCaret"])
		settingsSizer.Add(self.followCaretCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# review cursor settings dialog.
		self.followMouseCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Follow &mouse cursor"))
		self.followMouseCheckBox.SetValue(config.conf["reviewCursor"]["followMouse"])
		settingsSizer.Add(self.followMouseCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# review cursor settings dialog.
		self.simpleReviewModeCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Simple review mode"))
		self.simpleReviewModeCheckBox.SetValue(config.conf["reviewCursor"]["simpleReviewMode"])
		settingsSizer.Add(self.simpleReviewModeCheckBox,border=10,flag=wx.BOTTOM)

	def postInit(self):
		self.followFocusCheckBox.SetFocus()

	def onOk(self,evt):
		config.conf["reviewCursor"]["followFocus"]=self.followFocusCheckBox.IsChecked()
		config.conf["reviewCursor"]["followCaret"]=self.followCaretCheckBox.IsChecked()
		config.conf["reviewCursor"]["followMouse"]=self.followMouseCheckBox.IsChecked()
		config.conf["reviewCursor"]["simpleReviewMode"]=self.simpleReviewModeCheckBox.IsChecked()
		super(ReviewCursorDialog, self).onOk(evt)

class InputCompositionDialog(SettingsDialog):
	# Translators: This is the label for the Input Composition settings dialog.
	title = _("Input Composition Settings")

	def makeSettings(self, settingsSizer):
		# Translators: This is the label for a checkbox in the
		# Input composition settings dialog.
		self.autoReportAllCandidatesCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Automatically report all available &candidates"))
		self.autoReportAllCandidatesCheckBox.SetValue(config.conf["inputComposition"]["autoReportAllCandidates"])
		settingsSizer.Add(self.autoReportAllCandidatesCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# Input composition settings dialog.
		self.announceSelectedCandidateCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Announce &selected candidate"))
		self.announceSelectedCandidateCheckBox.SetValue(config.conf["inputComposition"]["announceSelectedCandidate"])
		settingsSizer.Add(self.announceSelectedCandidateCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# Input composition settings dialog.
		self.candidateIncludesShortCharacterDescriptionCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Always include short character &description when announcing candidates"))
		self.candidateIncludesShortCharacterDescriptionCheckBox.SetValue(config.conf["inputComposition"]["alwaysIncludeShortCharacterDescriptionInCandidateName"])
		settingsSizer.Add(self.candidateIncludesShortCharacterDescriptionCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# Input composition settings dialog.
		self.reportReadingStringChangesCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report changes to the &reading string"))
		self.reportReadingStringChangesCheckBox.SetValue(config.conf["inputComposition"]["reportReadingStringChanges"])
		settingsSizer.Add(self.reportReadingStringChangesCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# Input composition settings dialog.
		self.reportCompositionStringChangesCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report changes to the &composition string"))
		self.reportCompositionStringChangesCheckBox.SetValue(config.conf["inputComposition"]["reportCompositionStringChanges"])
		settingsSizer.Add(self.reportCompositionStringChangesCheckBox,border=10,flag=wx.BOTTOM)

	def postInit(self):
		self.autoReportAllCandidatesCheckBox.SetFocus()

	def onOk(self,evt):
		config.conf["inputComposition"]["autoReportAllCandidates"]=self.autoReportAllCandidatesCheckBox.IsChecked()
		config.conf["inputComposition"]["announceSelectedCandidate"]=self.announceSelectedCandidateCheckBox.IsChecked()
		config.conf["inputComposition"]["alwaysIncludeShortCharacterDescriptionInCandidateName"]=self.candidateIncludesShortCharacterDescriptionCheckBox.IsChecked()
		config.conf["inputComposition"]["reportReadingStringChanges"]=self.reportReadingStringChangesCheckBox.IsChecked()
		config.conf["inputComposition"]["reportCompositionStringChanges"]=self.reportCompositionStringChangesCheckBox.IsChecked()
		super(InputCompositionDialog, self).onOk(evt)

class ObjectPresentationDialog(SettingsDialog):
	# Translators: This is the label for the object presentation dialog.
	title = _("Object Presentation")
	progressLabels = (
		# Translators: An option for progress bar output in the Object Presentation dialog
		# which disables reporting of progress bars.
		# See Progress bar output in the Object Presentation Settings section of the User Guide.
		("off", _("off")),
		# Translators: An option for progress bar output in the Object Presentation dialog
		# which reports progress bar updates by speaking.
		# See Progress bar output in the Object Presentation Settings section of the User Guide.
		("speak", _("Speak")),
		# Translators: An option for progress bar output in the Object Presentation dialog
		# which reports progress bar updates by beeping.
		# See Progress bar output in the Object Presentation Settings section of the User Guide.
		("beep", _("Beep")),
		# Translators: An option for progress bar output in the Object Presentation dialog
		# which reports progress bar updates by both speaking and beeping.
		# See Progress bar output in the Object Presentation Settings section of the User Guide.
		("both", _("Speak and beep")),
	)

	def makeSettings(self, settingsSizer):
		# Translators: This is the label for a checkbox in the
		# object presentation settings dialog.
		self.tooltipCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report &tooltips"))
		self.tooltipCheckBox.SetValue(config.conf["presentation"]["reportTooltips"])
		settingsSizer.Add(self.tooltipCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# object presentation settings dialog.
		self.balloonCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report &help balloons"))
		self.balloonCheckBox.SetValue(config.conf["presentation"]["reportHelpBalloons"])
		settingsSizer.Add(self.balloonCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# object presentation settings dialog.
		self.shortcutCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report object shortcut &keys"))
		self.shortcutCheckBox.SetValue(config.conf["presentation"]["reportKeyboardShortcuts"])
		settingsSizer.Add(self.shortcutCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# object presentation settings dialog.
		self.positionInfoCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report object &position information"))
		self.positionInfoCheckBox.SetValue(config.conf["presentation"]["reportObjectPositionInformation"])
		settingsSizer.Add(self.positionInfoCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# object presentation settings dialog.
		self.guessPositionInfoCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Guess object &position information when unavailable"))
		self.guessPositionInfoCheckBox.SetValue(config.conf["presentation"]["guessObjectPositionInformationWhenUnavailable"])
		settingsSizer.Add(self.guessPositionInfoCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# object presentation settings dialog.
		self.descriptionCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report object &descriptions"))
		self.descriptionCheckBox.SetValue(config.conf["presentation"]["reportObjectDescriptions"])
		settingsSizer.Add(self.descriptionCheckBox,border=10,flag=wx.BOTTOM)
		progressSizer=wx.BoxSizer(wx.HORIZONTAL)
		# Translators: This is the label for a combobox in the
		# object presentation settings dialog.
		progressLabel=wx.StaticText(self,-1,label=_("Progress &bar output:"))
		progressSizer.Add(progressLabel)
		progressListID=wx.NewId()
		# Translators: This is the name of a combobox in the
		# object presentation settings dialog.
		self.progressList=wx.Choice(self,progressListID,name=_("Progress bar output"),choices=[name for setting, name in self.progressLabels])
		for index, (setting, name) in enumerate(self.progressLabels):
			if setting == config.conf["presentation"]["progressBarUpdates"]["progressBarOutputMode"]:
				self.progressList.SetSelection(index)
				break
		else:
			log.debugWarning("Could not set progress list to current report progress bar updates setting")
		progressSizer.Add(self.progressList)
		settingsSizer.Add(progressSizer,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# object presentation settings dialog.
		self.reportBackgroundProgressBarsCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report background progress bars"))
		self.reportBackgroundProgressBarsCheckBox.SetValue(config.conf["presentation"]["progressBarUpdates"]["reportBackgroundProgressBars"])
		settingsSizer.Add(self.reportBackgroundProgressBarsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# object presentation settings dialog.
		self.dynamicContentCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report dynamic &content changes"))
		self.dynamicContentCheckBox.SetValue(config.conf["presentation"]["reportDynamicContentChanges"])
		settingsSizer.Add(self.dynamicContentCheckBox,border=10,flag=wx.BOTTOM)

	def postInit(self):
		self.tooltipCheckBox.SetFocus()

	def onOk(self,evt):
		config.conf["presentation"]["reportTooltips"]=self.tooltipCheckBox.IsChecked()
		config.conf["presentation"]["reportHelpBalloons"]=self.balloonCheckBox.IsChecked()
		config.conf["presentation"]["reportKeyboardShortcuts"]=self.shortcutCheckBox.IsChecked()
		config.conf["presentation"]["reportObjectPositionInformation"]=self.positionInfoCheckBox.IsChecked()
		config.conf["presentation"]["guessObjectPositionInformationWhenUnavailable"]=self.guessPositionInfoCheckBox.IsChecked()
		config.conf["presentation"]["reportObjectDescriptions"]=self.descriptionCheckBox.IsChecked()
		config.conf["presentation"]["progressBarUpdates"]["progressBarOutputMode"]=self.progressLabels[self.progressList.GetSelection()][0]
		config.conf["presentation"]["progressBarUpdates"]["reportBackgroundProgressBars"]=self.reportBackgroundProgressBarsCheckBox.IsChecked()
		config.conf["presentation"]["reportDynamicContentChanges"]=self.dynamicContentCheckBox.IsChecked()
		super(ObjectPresentationDialog, self).onOk(evt)

class BrowseModeDialog(SettingsDialog):
	# Translators: This is the label for the browse mode settings dialog.
	title = _("Browse Mode")

	def makeSettings(self, settingsSizer):
		# Translators: This is the label for a textfield in the
		# browse mode settings dialog.
		maxLengthLabel=wx.StaticText(self,-1,label=_("&Maximum number of characters on one line"))
		settingsSizer.Add(maxLengthLabel)
		self.maxLengthEdit=wx.TextCtrl(self,wx.NewId())
		self.maxLengthEdit.SetValue(str(config.conf["virtualBuffers"]["maxLineLength"]))
		settingsSizer.Add(self.maxLengthEdit,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a textfield in the
		# browse mode settings dialog.
		pageLinesLabel=wx.StaticText(self,-1,label=_("&Number of lines per page"))
		settingsSizer.Add(pageLinesLabel)
		self.pageLinesEdit=wx.TextCtrl(self,wx.NewId())
		self.pageLinesEdit.SetValue(str(config.conf["virtualBuffers"]["linesPerPage"]))
		settingsSizer.Add(self.pageLinesEdit,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# browse mode settings dialog.
		self.useScreenLayoutCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Use &screen layout (when supported)"))
		self.useScreenLayoutCheckBox.SetValue(config.conf["virtualBuffers"]["useScreenLayout"])
		settingsSizer.Add(self.useScreenLayoutCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# browse mode settings dialog.
		self.autoSayAllCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Automatic &Say All on page load"))
		self.autoSayAllCheckBox.SetValue(config.conf["virtualBuffers"]["autoSayAllOnPageLoad"])
		settingsSizer.Add(self.autoSayAllCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# browse mode settings dialog.
		self.layoutTablesCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report l&ayout tables"))
		self.layoutTablesCheckBox.SetValue(config.conf["documentFormatting"]["includeLayoutTables"])
		settingsSizer.Add(self.layoutTablesCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# browse mode settings dialog.
		self.autoPassThroughOnFocusChangeCheckBox=wx.CheckBox(self,wx.ID_ANY,label=_("Automatic focus mode for focus changes"))
		self.autoPassThroughOnFocusChangeCheckBox.SetValue(config.conf["virtualBuffers"]["autoPassThroughOnFocusChange"])
		settingsSizer.Add(self.autoPassThroughOnFocusChangeCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# browse mode settings dialog.
		self.autoPassThroughOnCaretMoveCheckBox=wx.CheckBox(self,wx.ID_ANY,label=_("Automatic focus mode for caret movement"))
		self.autoPassThroughOnCaretMoveCheckBox.SetValue(config.conf["virtualBuffers"]["autoPassThroughOnCaretMove"])
		settingsSizer.Add(self.autoPassThroughOnCaretMoveCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# browse mode settings dialog.
		self.passThroughAudioIndicationCheckBox=wx.CheckBox(self,wx.ID_ANY,label=_("Audio indication of focus and browse modes"))
		self.passThroughAudioIndicationCheckBox.SetValue(config.conf["virtualBuffers"]["passThroughAudioIndication"])
		settingsSizer.Add(self.passThroughAudioIndicationCheckBox,border=10,flag=wx.BOTTOM)

	def postInit(self):
		self.maxLengthEdit.SetFocus()

	def onOk(self,evt):
		try:
			newMaxLength=int(self.maxLengthEdit.GetValue())
		except:
			newMaxLength=0
		if newMaxLength >=10 and newMaxLength <=250:
			config.conf["virtualBuffers"]["maxLineLength"]=newMaxLength
		try:
			newPageLines=int(self.pageLinesEdit.GetValue())
		except:
			newPageLines=0
		if newPageLines >=5 and newPageLines <=150:
			config.conf["virtualBuffers"]["linesPerPage"]=newPageLines
		config.conf["virtualBuffers"]["useScreenLayout"]=self.useScreenLayoutCheckBox.IsChecked()
		config.conf["virtualBuffers"]["autoSayAllOnPageLoad"]=self.autoSayAllCheckBox.IsChecked()
		config.conf["documentFormatting"]["includeLayoutTables"]=self.layoutTablesCheckBox.IsChecked()
		config.conf["virtualBuffers"]["autoPassThroughOnFocusChange"]=self.autoPassThroughOnFocusChangeCheckBox.IsChecked()
		config.conf["virtualBuffers"]["autoPassThroughOnCaretMove"]=self.autoPassThroughOnCaretMoveCheckBox.IsChecked()
		config.conf["virtualBuffers"]["passThroughAudioIndication"]=self.passThroughAudioIndicationCheckBox.IsChecked()
		super(BrowseModeDialog, self).onOk(evt)

class DocumentFormattingDialog(SettingsDialog):
	# Translators: This is the label for the document formatting dialog.
	title = _("Document Formatting")

	def makeSettings(self, settingsSizer):
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.detectFormatAfterCursorCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Announce formatting changes after the cursor (can cause a lag)"))
		self.detectFormatAfterCursorCheckBox.SetValue(config.conf["documentFormatting"]["detectFormatAfterCursor"])
		settingsSizer.Add(self.detectFormatAfterCursorCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.fontNameCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report font &name"))
		self.fontNameCheckBox.SetValue(config.conf["documentFormatting"]["reportFontName"])
		settingsSizer.Add(self.fontNameCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.fontSizeCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report font &size"))
		self.fontSizeCheckBox.SetValue(config.conf["documentFormatting"]["reportFontSize"])
		settingsSizer.Add(self.fontSizeCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.fontAttrsCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report font attri&butes"))
		self.fontAttrsCheckBox.SetValue(config.conf["documentFormatting"]["reportFontAttributes"])
		settingsSizer.Add(self.fontAttrsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.alignmentCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report &alignment"))
		self.alignmentCheckBox.SetValue(config.conf["documentFormatting"]["reportAlignment"])
		settingsSizer.Add(self.alignmentCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.colorCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report &colors"))
		self.colorCheckBox.SetValue(config.conf["documentFormatting"]["reportColor"])
		settingsSizer.Add(self.colorCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.styleCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report st&yle"))
		self.styleCheckBox.SetValue(config.conf["documentFormatting"]["reportStyle"])
		settingsSizer.Add(self.styleCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.spellingErrorsCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report spelling errors"))
		self.spellingErrorsCheckBox.SetValue(config.conf["documentFormatting"]["reportSpellingErrors"])
		settingsSizer.Add(self.spellingErrorsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.pageCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report &pages"))
		self.pageCheckBox.SetValue(config.conf["documentFormatting"]["reportPage"])
		settingsSizer.Add(self.pageCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.lineNumberCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report &line numbers"))
		self.lineNumberCheckBox.SetValue(config.conf["documentFormatting"]["reportLineNumber"])
		settingsSizer.Add(self.lineNumberCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This message is presented in the document formatting settings dialogue
		# If this option is selected, NVDA will cound the leading spaces and tabs of a line and speak it.
		#
		self.lineIndentationCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report l&ine indentation"))
		self.lineIndentationCheckBox.SetValue(config.conf["documentFormatting"]["reportLineIndentation"])
		settingsSizer.Add(self.lineIndentationCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.tablesCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report &tables"))
		self.tablesCheckBox.SetValue(config.conf["documentFormatting"]["reportTables"])
		settingsSizer.Add(self.tablesCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.tableHeadersCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report table row/column h&eaders"))
		self.tableHeadersCheckBox.SetValue(config.conf["documentFormatting"]["reportTableHeaders"])
		settingsSizer.Add(self.tableHeadersCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.tableCellCoordsCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report table cell c&oordinates"))
		self.tableCellCoordsCheckBox.SetValue(config.conf["documentFormatting"]["reportTableCellCoords"])
		settingsSizer.Add(self.tableCellCoordsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.linksCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report &links"))
		self.linksCheckBox.SetValue(config.conf["documentFormatting"]["reportLinks"])
		settingsSizer.Add(self.linksCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.headingsCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report &headings"))
		self.headingsCheckBox.SetValue(config.conf["documentFormatting"]["reportHeadings"])
		settingsSizer.Add(self.headingsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.listsCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report l&ists"))
		self.listsCheckBox.SetValue(config.conf["documentFormatting"]["reportLists"])
		settingsSizer.Add(self.listsCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.blockQuotesCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report block &quotes"))
		self.blockQuotesCheckBox.SetValue(config.conf["documentFormatting"]["reportBlockQuotes"])
		settingsSizer.Add(self.blockQuotesCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		self.landmarksCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Report lan&dmarks"))
		self.landmarksCheckBox.SetValue(config.conf["documentFormatting"]["reportLandmarks"])
		settingsSizer.Add(self.landmarksCheckBox,border=10,flag=wx.BOTTOM)
		# Translators: This is the label for a checkbox in the
		# document formatting settings dialog.
		item=self.framesCheckBox=wx.CheckBox(self,label=_("Report fra&mes"))
		item.Value=config.conf["documentFormatting"]["reportFrames"]
		settingsSizer.Add(item,border=10,flag=wx.BOTTOM)

	def postInit(self):
		self.detectFormatAfterCursorCheckBox.SetFocus()

	def onOk(self,evt):
		config.conf["documentFormatting"]["detectFormatAfterCursor"]=self.detectFormatAfterCursorCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportFontName"]=self.fontNameCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportFontSize"]=self.fontSizeCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportFontAttributes"]=self.fontAttrsCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportColor"]=self.colorCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportAlignment"]=self.alignmentCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportStyle"]=self.styleCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportSpellingErrors"]=self.spellingErrorsCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportPage"]=self.pageCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportLineNumber"]=self.lineNumberCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportLineIndentation"]=self.lineIndentationCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportTables"]=self.tablesCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportTableHeaders"]=self.tableHeadersCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportTableCellCoords"]=self.tableCellCoordsCheckBox.IsChecked() 
		config.conf["documentFormatting"]["reportLinks"]=self.linksCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportHeadings"]=self.headingsCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportLists"]=self.listsCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportBlockQuotes"]=self.blockQuotesCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportLandmarks"]=self.landmarksCheckBox.IsChecked()
		config.conf["documentFormatting"]["reportFrames"]=self.framesCheckBox.Value
		super(DocumentFormattingDialog, self).onOk(evt)

class DictionaryEntryDialog(wx.Dialog):

	# Translators: This is the label for the edit dictionary entry dialog.
	def __init__(self, parent, title=_("Edit Dictionary Entry")):
		super(DictionaryEntryDialog,self).__init__(parent,title=title)
		mainSizer=wx.BoxSizer(wx.VERTICAL)
		settingsSizer=wx.BoxSizer(wx.VERTICAL)
		settingsSizer.Add(wx.StaticText(self,-1,label=_("&Pattern")))
		self.patternTextCtrl=wx.TextCtrl(self,wx.NewId())
		settingsSizer.Add(self.patternTextCtrl)
		settingsSizer.Add(wx.StaticText(self,-1,label=_("&Replacement")))
		self.replacementTextCtrl=wx.TextCtrl(self,wx.NewId())
		settingsSizer.Add(self.replacementTextCtrl)
		settingsSizer.Add(wx.StaticText(self,-1,label=_("&Comment")))
		self.commentTextCtrl=wx.TextCtrl(self,wx.NewId())
		settingsSizer.Add(self.commentTextCtrl)
		self.caseSensitiveCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Case &sensitive"))
		settingsSizer.Add(self.caseSensitiveCheckBox)
		self.regexpCheckBox=wx.CheckBox(self,wx.NewId(),label=_("Regular &expression"))
		settingsSizer.Add(self.regexpCheckBox)
		mainSizer.Add(settingsSizer,border=20,flag=wx.LEFT|wx.RIGHT|wx.TOP)
		buttonSizer=self.CreateButtonSizer(wx.OK|wx.CANCEL)
		mainSizer.Add(buttonSizer,border=20,flag=wx.LEFT|wx.RIGHT|wx.BOTTOM)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.patternTextCtrl.SetFocus()

class DictionaryDialog(SettingsDialog):

	def __init__(self,parent,title,speechDict):
		self.title = title
		self.speechDict = speechDict
		self.tempSpeechDict=speechDictHandler.SpeechDict()
		self.tempSpeechDict.extend(self.speechDict)
		globalVars.speechDictionaryProcessing=False
		super(DictionaryDialog, self).__init__(parent)

	def makeSettings(self, settingsSizer):
		dictListID=wx.NewId()
		entriesSizer=wx.BoxSizer(wx.VERTICAL)
		entriesLabel=wx.StaticText(self,-1,label=_("&Dictionary entries"))
		entriesSizer.Add(entriesLabel)
		self.dictList=wx.ListCtrl(self,dictListID,style=wx.LC_REPORT|wx.LC_SINGLE_SEL,size=(550,350))
		self.dictList.InsertColumn(0,_("Comment"),width=150)
		self.dictList.InsertColumn(1,_("Pattern"),width=150)
		self.dictList.InsertColumn(2,_("Replacement"),width=150)
		self.dictList.InsertColumn(3,_("case"),width=50)
		self.dictList.InsertColumn(4,_("Regexp"),width=50)
		self.offOn = (_("off"),_("on"))
		for entry in self.tempSpeechDict:
			self.dictList.Append((entry.comment,entry.pattern,entry.replacement,self.offOn[int(entry.caseSensitive)],self.offOn[int(entry.regexp)]))
		self.editingIndex=-1
		entriesSizer.Add(self.dictList,proportion=8)
		settingsSizer.Add(entriesSizer)
		entryButtonsSizer=wx.BoxSizer(wx.HORIZONTAL)
		addButtonID=wx.NewId()
		addButton=wx.Button(self,addButtonID,_("&Add"),wx.DefaultPosition)
		entryButtonsSizer.Add(addButton)
		editButtonID=wx.NewId()
		editButton=wx.Button(self,editButtonID,_("&Edit"),wx.DefaultPosition)
		entryButtonsSizer.Add(editButton)
		removeButtonID=wx.NewId()
		removeButton=wx.Button(self,removeButtonID,_("&Remove"),wx.DefaultPosition)
		entryButtonsSizer.Add(removeButton)
		self.Bind(wx.EVT_BUTTON,self.OnAddClick,id=addButtonID)
		self.Bind(wx.EVT_BUTTON,self.OnEditClick,id=editButtonID)
		self.Bind(wx.EVT_BUTTON,self.OnRemoveClick,id=removeButtonID)
		settingsSizer.Add(entryButtonsSizer)

	def postInit(self):
		self.dictList.SetFocus()

	def onCancel(self,evt):
		globalVars.speechDictionaryProcessing=True
		super(DictionaryDialog, self).onCancel(evt)

	def onOk(self,evt):
		globalVars.speechDictionaryProcessing=True
		if self.tempSpeechDict!=self.speechDict:
			del self.speechDict[:]
			self.speechDict.extend(self.tempSpeechDict)
			self.speechDict.save()
		super(DictionaryDialog, self).onOk(evt)

	def OnAddClick(self,evt):
		# Translators: This is the label for the add dictionary entry dialog.
		entryDialog=DictionaryEntryDialog(self,title=_("Add Dictionary Entry"))
		if entryDialog.ShowModal()==wx.ID_OK:
			self.tempSpeechDict.append(speechDictHandler.SpeechDictEntry(entryDialog.patternTextCtrl.GetValue(),entryDialog.replacementTextCtrl.GetValue(),entryDialog.commentTextCtrl.GetValue(),bool(entryDialog.caseSensitiveCheckBox.GetValue()),bool(entryDialog.regexpCheckBox.GetValue())))
			self.dictList.Append((entryDialog.commentTextCtrl.GetValue(),entryDialog.patternTextCtrl.GetValue(),entryDialog.replacementTextCtrl.GetValue(),self.offOn[int(entryDialog.caseSensitiveCheckBox.GetValue())],self.offOn[int(entryDialog.regexpCheckBox.GetValue())]))
			index=self.dictList.GetFirstSelected()
			while index>=0:
				self.dictList.Select(index,on=0)
				index=self.dictList.GetNextSelected(index)
			addedIndex=self.dictList.GetItemCount()-1
			self.dictList.Select(addedIndex)
			self.dictList.Focus(addedIndex)
			self.dictList.SetFocus()
		entryDialog.Destroy()

	def OnEditClick(self,evt):
		if self.dictList.GetSelectedItemCount()!=1:
			return
		editIndex=self.dictList.GetFirstSelected()
		if editIndex<0:
			return
		entryDialog=DictionaryEntryDialog(self)
		entryDialog.patternTextCtrl.SetValue(self.tempSpeechDict[editIndex].pattern)
		entryDialog.replacementTextCtrl.SetValue(self.tempSpeechDict[editIndex].replacement)
		entryDialog.commentTextCtrl.SetValue(self.tempSpeechDict[editIndex].comment)
		entryDialog.caseSensitiveCheckBox.SetValue(self.tempSpeechDict[editIndex].caseSensitive)
		entryDialog.regexpCheckBox.SetValue(self.tempSpeechDict[editIndex].regexp)
		if entryDialog.ShowModal()==wx.ID_OK:
			self.tempSpeechDict[editIndex]=speechDictHandler.SpeechDictEntry(entryDialog.patternTextCtrl.GetValue(),entryDialog.replacementTextCtrl.GetValue(),entryDialog.commentTextCtrl.GetValue(),bool(entryDialog.caseSensitiveCheckBox.GetValue()),bool(entryDialog.regexpCheckBox.GetValue()))
			self.dictList.SetStringItem(editIndex,0,entryDialog.commentTextCtrl.GetValue())
			self.dictList.SetStringItem(editIndex,1,entryDialog.patternTextCtrl.GetValue())
			self.dictList.SetStringItem(editIndex,2,entryDialog.replacementTextCtrl.GetValue())
			self.dictList.SetStringItem(editIndex,3,self.offOn[int(entryDialog.caseSensitiveCheckBox.GetValue())])
			self.dictList.SetStringItem(editIndex,4,self.offOn[int(entryDialog.regexpCheckBox.GetValue())])
			self.dictList.SetFocus()
		entryDialog.Destroy()

	def OnRemoveClick(self,evt):
		index=self.dictList.GetFirstSelected()
		while index>=0:
			self.dictList.DeleteItem(index)
			del self.tempSpeechDict[index]
			index=self.dictList.GetNextSelected(index)
		self.dictList.SetFocus()

class BrailleSettingsDialog(SettingsDialog):
	# Translators: This is the label for the braille settings dialog.
	title = _("Braille Settings")

	def makeSettings(self, settingsSizer):
		sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, wx.ID_ANY, label=_("Braille &display:"))
		driverList = braille.getDisplayList()
		self.displayNames = [driver[0] for driver in driverList]
		self.displayList = wx.Choice(self, wx.ID_ANY, choices=[driver[1] for driver in driverList])
		self.Bind(wx.EVT_CHOICE, self.onDisplayNameChanged, self.displayList)
		try:
			selection = self.displayNames.index(braille.handler.display.name)
			self.displayList.SetSelection(selection)
		except:
			pass
		sizer.Add(label)
		sizer.Add(self.displayList)
		settingsSizer.Add(sizer, border=10, flag=wx.BOTTOM)

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, wx.ID_ANY, label=_("&Port:"))
		self.portsList = wx.Choice(self, wx.ID_ANY, choices=[])
		sizer.Add(label)
		sizer.Add(self.portsList)
		settingsSizer.Add(sizer, border=10, flag=wx.BOTTOM)
		self.updatePossiblePorts()

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, wx.ID_ANY, label=_("&Output table:"))
		self.tableNames = [table[0] for table in braille.TABLES]
		self.tableList = wx.Choice(self, wx.ID_ANY, choices=[table[1] for table in braille.TABLES])
		try:
			selection = self.tableNames.index(config.conf["braille"]["translationTable"])
			self.tableList.SetSelection(selection)
		except:
			pass
		sizer.Add(label)
		sizer.Add(self.tableList)
		settingsSizer.Add(sizer, border=10, flag=wx.BOTTOM)

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, wx.ID_ANY, label=_("&Input table:"))
		self.inputTableNames = [table[0] for table in braille.INPUT_TABLES]
		self.inputTableList = wx.Choice(self, wx.ID_ANY, choices=[table[1] for table in braille.INPUT_TABLES])
		try:
			selection = self.inputTableNames.index(config.conf["braille"]["inputTable"])
			self.inputTableList.SetSelection(selection)
		except:
			pass
		sizer.Add(label)
		sizer.Add(self.inputTableList)
		settingsSizer.Add(sizer, border=10, flag=wx.BOTTOM)

		self.expandAtCursorCheckBox = wx.CheckBox(self, wx.ID_ANY, label=_("E&xpand to computer braille for the word at the cursor"))
		self.expandAtCursorCheckBox.SetValue(config.conf["braille"]["expandAtCursor"])
		settingsSizer.Add(self.expandAtCursorCheckBox, border=10, flag=wx.BOTTOM)

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, wx.ID_ANY, label=_("Cursor blink rate (ms)"))
		sizer.Add(label)
		self.cursorBlinkRateEdit = wx.TextCtrl(self, wx.ID_ANY)
		self.cursorBlinkRateEdit.SetValue(str(config.conf["braille"]["cursorBlinkRate"]))
		sizer.Add(self.cursorBlinkRateEdit)
		settingsSizer.Add(sizer, border=10, flag=wx.BOTTOM)

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, wx.ID_ANY, label=_("Message timeout (sec)"))
		sizer.Add(label)
		self.messageTimeoutEdit = wx.TextCtrl(self, wx.ID_ANY)
		self.messageTimeoutEdit.SetValue(str(config.conf["braille"]["messageTimeout"]))
		sizer.Add(self.messageTimeoutEdit)
		settingsSizer.Add(sizer, border=10, flag=wx.BOTTOM)

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		label = wx.StaticText(self, wx.ID_ANY, label=_("Braille tethered to:"))
		self.tetherValues=[("focus",_("focus")),("review",_("review"))]
		self.tetherList = wx.Choice(self, wx.ID_ANY, choices=[x[1] for x in self.tetherValues])
		tetherConfig=braille.handler.tether
		selection = (x for x,y in enumerate(self.tetherValues) if y[0]==tetherConfig).next()  
		try:
			self.tetherList.SetSelection(selection)
		except:
			pass
		sizer.Add(label)
		sizer.Add(self.tetherList)
		settingsSizer.Add(sizer, border=10, flag=wx.BOTTOM)

		item = self.readByParagraphCheckBox = wx.CheckBox(self, label=_("Read by &paragraph"))
		item.Value = config.conf["braille"]["readByParagraph"]
		settingsSizer.Add(item, border=10, flag=wx.BOTTOM)

		item = self.wordWrapCheckBox = wx.CheckBox(self, label=_("Avoid splitting &words when possible"))
		item.Value = config.conf["braille"]["wordWrap"]
		settingsSizer.Add(item, border=10, flag=wx.BOTTOM)

	def postInit(self):
		self.displayList.SetFocus()

	def onOk(self, evt):
		display = self.displayNames[self.displayList.GetSelection()]
		if display not in config.conf["braille"]:
			config.conf["braille"][display] = {}
		if self.possiblePorts:
			port = self.possiblePorts[self.portsList.GetSelection()][0]
			config.conf["braille"][display]["port"] = port
		if not braille.handler.setDisplayByName(display):
			gui.messageBox(_("Could not load the %s display.")%display, _("Braille Display Error"), wx.OK|wx.ICON_WARNING, self)
			return 
		config.conf["braille"]["translationTable"] = self.tableNames[self.tableList.GetSelection()]
		config.conf["braille"]["inputTable"] = self.inputTableNames[self.inputTableList.GetSelection()]
		config.conf["braille"]["expandAtCursor"] = self.expandAtCursorCheckBox.GetValue()
		try:
			val = int(self.cursorBlinkRateEdit.GetValue())
		except (ValueError, TypeError):
			val = None
		if 0 <= val <= 2000:
			config.conf["braille"]["cursorBlinkRate"] = val
		try:
			val = int(self.messageTimeoutEdit.GetValue())
		except (ValueError, TypeError):
			val = None
		if 1 <= val <= 20:
			config.conf["braille"]["messageTimeout"] = val
		braille.handler.tether = self.tetherValues[self.tetherList.GetSelection()][0]
		config.conf["braille"]["readByParagraph"] = self.readByParagraphCheckBox.Value
		config.conf["braille"]["wordWrap"] = self.wordWrapCheckBox.Value
		super(BrailleSettingsDialog,  self).onOk(evt)

	def onDisplayNameChanged(self, evt):
		self.updatePossiblePorts()

	def updatePossiblePorts(self):
		displayName = self.displayNames[self.displayList.GetSelection()]
		displayCls = braille._getDisplayDriver(displayName)
		self.possiblePorts = []
		try:
			self.possiblePorts.extend(displayCls.getPossiblePorts().iteritems())
		except NotImplementedError:
			pass
		if self.possiblePorts:
			self.portsList.SetItems([p[1] for p in self.possiblePorts])
			try:
				selectedPort = config.conf["braille"][displayName].get("port")
				portNames = [p[0] for p in self.possiblePorts]
				selection = portNames.index(selectedPort)
			except (KeyError, ValueError):
				# Display name not in config or port not valid
				selection = 0
			self.portsList.SetSelection(selection)
		# If no port selection is possible or only automatic selection is available, disable the port selection control
		enable = len(self.possiblePorts) > 0 and not (len(self.possiblePorts) == 1 and self.possiblePorts[0][0] == "auto")
		self.portsList.Enable(enable)

class SpeechSymbolsDialog(SettingsDialog):
	# Translators: This is the label for the symbol pronunciation dialog.
	title = _("Symbol Pronunciation")

	def makeSettings(self, settingsSizer):
		try:
			symbolProcessor = characterProcessing._localeSpeechSymbolProcessors.fetchLocaleData(languageHandler.getLanguage())
		except LookupError:
			symbolProcessor = characterProcessing._localeSpeechSymbolProcessors.fetchLocaleData("en")
		self.symbolProcessor = symbolProcessor
		symbols = self.symbols = [copy.copy(symbol) for symbol in self.symbolProcessor.computedSymbols.itervalues()]

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(wx.StaticText(self, wx.ID_ANY, _("&Symbols")))
		self.symbolsList = wx.ListCtrl(self, wx.ID_ANY, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(360, 350))
		self.symbolsList.InsertColumn(0, _("Symbol"), width=150)
		self.symbolsList.InsertColumn(1, _("Replacement"), width=150)
		self.symbolsList.InsertColumn(2, _("Level"), width=60)
		for symbol in symbols:
			item = self.symbolsList.Append((symbol.displayName,))
			self.updateListItem(item, symbol)
		self.symbolsList.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.onListItemFocused)
		self.symbolsList.Bind(wx.EVT_CHAR, self.onListChar)
		sizer.Add(self.symbolsList)
		settingsSizer.Add(sizer)

		changeSizer = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, _("Change symbol")), wx.VERTICAL)
		sizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(wx.StaticText(self, wx.ID_ANY, _("&Replacement")))
		self.replacementEdit = wx.TextCtrl(self, wx.ID_ANY)
		self.replacementEdit.Bind(wx.EVT_KILL_FOCUS, self.onSymbolEdited)
		sizer.Add(self.replacementEdit)
		changeSizer.Add(sizer)
		sizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(wx.StaticText(self, wx.ID_ANY, _("&Level")))
		symbolLevelLabels = characterProcessing.SPEECH_SYMBOL_LEVEL_LABELS
		self.levelList = wx.Choice(self, wx.ID_ANY,choices=[
			symbolLevelLabels[level] for level in characterProcessing.SPEECH_SYMBOL_LEVELS])
		self.levelList.Bind(wx.EVT_KILL_FOCUS, self.onSymbolEdited)
		sizer.Add(self.levelList)
		changeSizer.Add(sizer)
		settingsSizer.Add(changeSizer)

		self.editingItem = None

	def postInit(self):
		self.symbolsList.SetFocus()

	def updateListItem(self, item, symbol):
		self.symbolsList.SetStringItem(item, 1, symbol.replacement)
		self.symbolsList.SetStringItem(item, 2, characterProcessing.SPEECH_SYMBOL_LEVEL_LABELS[symbol.level])

	def onSymbolEdited(self, evt):
		if self.editingItem is None:
			return
		# Update the symbol the user was just editing.
		item = self.editingItem
		symbol = self.symbols[item]
		symbol.replacement = self.replacementEdit.Value
		symbol.level = characterProcessing.SPEECH_SYMBOL_LEVELS[self.levelList.Selection]
		self.updateListItem(item, symbol)

	def onListItemFocused(self, evt):
		# Update the editing controls to reflect the newly selected symbol.
		item = evt.GetIndex()
		symbol = self.symbols[item]
		self.editingItem = item
		self.replacementEdit.Value = symbol.replacement
		self.levelList.Selection = characterProcessing.SPEECH_SYMBOL_LEVELS.index(symbol.level)

	def onListChar(self, evt):
		if evt.KeyCode == wx.WXK_RETURN:
			# The enter key should be propagated to the dialog and thus activate the default button,
			# but this is broken (wx ticket #3725).
			# Therefore, we must catch the enter key here.
			# Activate the OK button.
			self.ProcessEvent(wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_OK))

		else:
			evt.Skip()

	def onOk(self, evt):
		self.onSymbolEdited(None)
		self.editingItem = None
		for symbol in self.symbols:
			self.symbolProcessor.updateSymbol(symbol)
		try:
			self.symbolProcessor.userSymbols.save()
		except IOError as e:
			log.error("Error saving user symbols info: %s" % e)
		characterProcessing._localeSpeechSymbolProcessors.invalidateLocaleData(self.symbolProcessor.locale)
		super(SpeechSymbolsDialog, self).onOk(evt)
