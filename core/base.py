"""
OWASP Maryam!

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
# Based on the Recon-ng core(https://github.com/lanmaster53/recon-ng)

# This file contains 2 classes AND spool_print() function
# 1. Base
# 2. Mode => console0 ,cli1 , gui2 



__version__ = "v1.4.9"
import argparse
import errno
import imp  #provides an interface to the mechanisms used to implement the import statement.
import os
import random
import re
import shutil #offers a number of high-level operations on files and collections of files.
import sys
import builtins #provides direct access to all ‘built-in’ identifiers of Python;  useful in modules that provide objects with the same name as a built-in value
import shlex #makes it easy to write lexical analyzers
import textwrap

from multiprocessing import Pool,Process
# Pool object which offers a convenient means of parallelizing the execution of a function across multiple input values, distributing the input data across processes (data parallelism)
#In multiprocessing, processes are spawned by creating a Process object and then calling its start() method


# import framework libs
from core import framework

from threading import Lock
_print_lock = Lock() #class implementing primitive lock objects. Once a thread has acquired a lock, subsequent attempts to acquire it block, until it is released; any thread may release it.


# spooling system
##Spooling is a process in which data is temporarily held to be used and executed by a device, program or the system
def spool_print(*args, **kwargs):
	with _print_lock:
		if framework.Framework._spool:
			framework.Framework._spool.write(f"{args[0]}{os.linesep}")
			framework.Framework._spool.flush()
		if "console" in kwargs and kwargs["console"] is False:
			return
		# new print function must still use the old print function via the
		# backup
		builtins._print(*args, **kwargs)


# make a builtin backup of the original print function
builtins._print = print
# override the builtin print function with the new print function
builtins.print = spool_print


# instance of this get executed during starting operation
class Base(framework.Framework):

	def __init__(self):
		framework.Framework.__init__(self, 'base')
		self._history_file = ''
		self._mode = 0
		self._config = {
				'name' : 'maryam',
				'module_ext' : '.py',
				'data_directory_name' : 'data',
				'module_directory_name' : 'modules',
				'workspaces_directory_name' : '.maryam/workspaces'
			}
		self._name = self._config['name']
		self._prompt_template = '%s[%s] > '
		self._base_prompt = self._prompt_template % ('', self._name)
		
		# establish dynamic paths for framework elements
		self.path = framework.Framework.app_path = sys.path[0]
		
		##app_path  => from framework class => ro get use self else to set use complete class name
		
		#data_path => data dir 
		#core_path => core dir
		#module_path => module dir
		#module_ext => module extention
		#module_dirname => modules
		#workspaces_dirname => .maryam/workspaces
		
		self.data_path = framework.Framework.data_path = os.path.join(
			self.app_path, self._config['data_directory_name'])
		
		self.core_path = framework.Framework.core_path = os.path.join(
			self.app_path, 'core')
		
		self.module_path = framework.Framework.module_path = os.path.join(
			self.app_path, self._config['module_directory_name'])
		
		self.module_ext = framework.Framework.module_ext = self._config[
			'module_ext']
		
		self.module_dirname = framework.Framework.module_dirname = self._config[
			'module_directory_name']
			
		
		self.workspaces_dirname = self._config['workspaces_directory_name']
		self.options = self._global_options
		self._init_global_options()
		self._init_home() # initialize home folder
		self.init_workspace('default') #create wkspc dir , change prompt , initHistory , load[config,modules]
		self._init_var()
		self._check_version() #make web request to check latest maryam version
		if self._mode == Mode.CONSOLE:  #Mode is support class defined at last
			self.show_banner()

	# ==================================================
	# SUPPORT METHODS
	# ==================================================
	
	#init global options => target ,proxy,limit,agent,rand_agent,timeout,verbosity,history
	def _init_global_options(self):
		#register_option from framework class
		self.register_option('target', 'example.com', True,
							 'target for default hostname')
		self.register_option('proxy', None, False,
							 'proxy server (address:port)')
		self.register_option(
			'agent', f'Mozilla/5.0 (X11; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0', True, 'user-agent string')
		self.register_option(
			'rand_agent', False, True, 'setting random user-agent')
		self.register_option('timeout', 10, True, 'socket timeout (seconds)')
		self.register_option(
			'verbosity', '1',True,
			'verbosity level (0 = minimal, 1 = verbose, 2 = debug)')
		self.register_option('history', True, False, 'logging all console inputs')
		self.register_option('update_check', True, False, 'checking the framework version before running')

	def _init_home(self):
		self._home = framework.Framework._home = os.path.expanduser('~')
		#print("initializing home folder")
		if not os.path.exists(self._home):
			os.makedirs(self._home)

	def _check_version(self):
		if self._global_options.get('update_check'):
			self.debug('Checking version...')
			pattern = r"__VERSION__ = '(\d+\.\d+\.\d+[^']*)'"
			remote = 0
			local = 0
			try:
				remote = re.search(pattern, self.request(\
					'https://raw.githubusercontent.com/saeeddhqan/maryam/master/maryam').text).group(1)
				local = re.search(pattern, open('maryam').read()).group(1)
			except Exception as e:
				self.error(f"Version check failed ({type(e).__name__}).")
			if remote != local:
				self.alert('Your version of Maryam does not match the latest release')
				self.output(f"Remote version:  {remote}")
				self.output(f"Local version:   {local}")

	
	
	def _load_modules(self):
		#print("=======loading_modules=======")
		self.loaded_category = {}
		self._loaded_modules = framework.Framework._loaded_modules
		
		# crawl the module directory and build the module tree
		for dirpath, dirnames, filenames in os.walk(self.module_path, followlinks=True):
			
			#in each itr give [pwd] [dir in pwd] [filenames in pwd] 	
			# remove hidden files and directories
			filenames = [f for f in filenames if not f[0] == '.']
			dirnames[:] = [d for d in dirnames if not d[0] == '.']
			if len(filenames) > 0:
				
				# for each .py file 
				for filename in [f for f in filenames if f.endswith(self.module_ext)]:
					is_loaded = self._load_module(dirpath, filename)
					mod_category = "disabled"
					if is_loaded:
						modules_reg = r'/' + \
							self.module_dirname + r"/([^/]*)"
						try:
							# trying to find module category [osint search footprint] using regex on filepath
							mod_category = re.search(
								modules_reg, dirpath).group(1)
						except AttributeError:
							mod_path = os.path.join(dirpath, filename)
							mod_category = re.search(modules_reg,
													 mod_path).group(1).replace(
								self.module_ext,
								'')

						# store the resulting category statistics
						if mod_category not in self.loaded_category:
							self.loaded_category[mod_category] = 0
						self.loaded_category[mod_category] += 1
		#print("==========modules loaded =========")
	def _load_module(self, dirpath, filename):
		#print(f"loading {filename}")
		mod_name = filename.split('.')[0]
		mod_dispname = '/'.join(re.split("/%s/" % self.module_dirname, dirpath)
								[-1].split('/') + [mod_name])
		mod_loadname = mod_dispname.replace("/", "_")
		mod_loadpath = os.path.join(dirpath, filename)
		
		#mod_name :  facebook
		#mod_dispname :  search/facebook
		#mod_loadname :  search_facebook  (replace / by _ in mod_dispname)
		#mod_loadpath :  /media/tarunesh1234/New_Volume_E1/Maryam/modules/search/facebook.py

		mod_file = open(mod_loadpath)
		
		try:
			# import the module into memory
			## dynamic explicit import  using python imp module
			##Load and initialize a module implemented as a Python source file and return its module object.
			##If the module was already initialized, it will be initialized again.
			imp.load_source(mod_loadname, mod_loadpath, mod_file)
			__import__(mod_loadname) #__import__() is a function that is called by the import statement.
			
			# add the module to the framework's loaded modules
			#print("check :" ,sys.modules[mod_loadname].Module(mod_dispname))
			
			#_loaded_modules stores tool's module object
			# sys.modules => dictionary that maps module names to modules which have already been loaded
			# type(sys.modules[mod_loadname]) =>module
			# Module() is defined in each tool's module file 
			self._loaded_modules[mod_dispname] = sys.modules[mod_loadname].Module(mod_dispname)
			self._module_names[mod_name] = mod_dispname
		
			return True
		except ImportError as e:
			# notify the user of missing dependencies
			self.error(f"Module \'{mod_dispname}\' disabled. Dependency required: {self.to_unicode_str(e)[16:]}")
		except:
			# notify the user of errors
			self.print_exception()  # from framework
			self.error(f"Module '{mod_dispname}' disabled.")
		# remove the module from the framework's loaded modules
		self._loaded_modules.pop(mod_dispname, None)
		if mod_name in self._module_names:
			self._module_names.pop(mod_name)

	# ==================================================
	# WORKSPACE METHODS
	# ==================================================
	
	#create wkspc dir , change prompt , initHistory , load[config,modules]
	def init_workspace(self, workspace):
		if not workspace:
			return
		
		#print(f"init_workspace {workspace}")
		#workspace =  home_dir + .maryam/workspaces/ + given_workspace_name
		workspace = os.path.join(self._home, self.workspaces_dirname, workspace)
		if not os.path.exists(workspace):
			os.makedirs(workspace)
			#print("init_workspace_dir")

		# set workspace attributes
		self.workspace = framework.Framework.workspace = workspace
		#print("changing prompt")
		self.prompt = self._prompt_template % (self._base_prompt[:-3], self.workspace.split('/')[-1])
		# load workspace configuration
		self._init_history()
		self._load_config()
		# load modules after config to pop_init_varulate options
		self._load_modules()
		return True

	def remove_workspace(self, workspace):
		path = os.path.join(self._home, self.workspaces_dirname, workspace)
		try:
			shutil.rmtree(path)
		except OSError:
			return False
		if workspace == self.workspace.split('/')[-1]:
			self.init_workspace("default")
		return True

	def _get_workspaces(self):
		dirnames = []
		path = os.path.join(self._home, self.workspaces_dirname)
		dirnames = [name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))]
		return dirnames

	# ==================================================
	# SHOW METHODS
	# ==================================================

	def show_banner(self):
		banner = open(os.path.join(self.data_path, "banner.txt")).read()
		print(banner)
		# print version
		print(' '*15 + __version__)
		print('')
		if self.loaded_category == {}:
			print(
				f'{framework.Colors.B}[0] No module to display{framework.Colors.N}')

		else:
			counts = [(self.loaded_category[x], x)
					  for x in self.loaded_category] if self.loaded_category != [] else [0]
			count_len = len(max([str(x[0]) for x in counts], key=len))
			for count in sorted(counts, reverse=True):
				cnt = f'[{count[0]}]'
				mod_name = count[1].title() if '/' in count[1] else count[1]
				print(f'{framework.Colors.B}{cnt.ljust(count_len + 2)} {mod_name} modules{framework.Colors.N}')
		print('')

	
	def show_workspaces(self):
		self.do_workspaces("list")

	#==================================================
	# HELP METHODS
	#==================================================

	def help_workspaces(self):
		print(getattr(self, "do_workspaces").__doc__)
		print(f'{os.linesep}Usage: workspaces [add|select|delete|list]{os.linesep}')

	# ==================================================
	# COMMAND METHODS
	# ==================================================

	def do_reload(self, params):
		'''Reloads all modules'''
		self.output(f"Reloading...")
		self._load_modules()

	def do_workspaces(self, params):
		'''Manages workspaces'''
		if not params:
			self.help_workspaces()
			return
		params = params.split()
		arg = params.pop(0).lower()
		if arg == 'list':
			header = '\nWorkspaces:\n'
			print(header + self.ruler * len(header[2:]))
			for i in self._get_workspaces():
				print(''.ljust(5) + i)
			print('')
		elif arg in ['add', 'select']:
			if len(params) == 1:
				if not self.init_workspace(params[0]):
					self.output(f"Unable to initialize '{params[0]}' workspace.")
			else:
				print('Usage: workspace [add|select|delete] <name>')
		elif arg == 'delete':
			if len(params) == 1:
				if not self.remove_workspace(params[0]):
					self.output(f"Unable to delete '{params[0]}' workspace.")
			else:
				print('Usage: workspace delete <name>')
		else:
			self.help_workspaces()

	def do_load(self, params):
		'''Loads specified module'''
		try:
			self._validate_options()
		except framework.FrameworkException as e:
			self.error(e.message)
			return
		if not params:
			self.help_load()
			return
		
		# finds any modules that contain params
		modules = [params] if params in self._loaded_modules else [
			x for x in self._loaded_modules if params in x]
		
		# notify the user if none or multiple modules are found
		if len(modules) != 1:
			if not modules:
				self.error('Invalid module name.')
			else:
				self.output(f"Multiple modules match '{params}'.")
				self.show_modules(modules)
			return
		
		# load the module
		mod_dispname = modules[0]
		
		# loop to support reload logic
		while True:
			y = self._loaded_modules[mod_dispname]
			mod_loadpath = os.path.abspath(sys.modules[y.__module__].__file__)

			# return the loaded module if in command line mode
			if self._mode == Mode.CLI:
				return y

			# begin a command loop
			y.prompt = self._prompt_template % (
					self.prompt[:-3], mod_dispname.split('/')[-1])
			try:
				y.cmdloop()
			except KeyboardInterrupt:
				print('')
			if y._exit == 1:
				return True
			if y._reload == 1:
				self.output("Reloading...")
				# reload the module in memory
				is_loaded = self._load_module(os.path.dirname(
					mod_loadpath), os.path.basename(mod_loadpath))
				if is_loaded:
					# reload the module in the framework
					continue
				# shuffle category counts?
			break

	do_use = do_load

	# ==================================================
	# TOOL/FUNCTION METHODS
	# ==================================================
	def opt_proc(self, tool_name, args=None, output=None):
		#module_name store module_dispname
		mod = self._loaded_modules[self._module_names[tool_name]]

		meta = mod.meta
		opts = meta['options']
		description = f'{tool_name}{meta["version"]}({meta["author"]}) - \tdescription: {meta["description"]}\n'
		parser = argparse.ArgumentParser(prog=tool_name, description=description)
		for option in opts:
			try:
				name, val, req, desc, op, act = option
			except ValueError as e:
				self.error(f"{tool_name}CodeError: options is too short. need more than {len(option)} option")
				return
			name = f"--{name}" if not name.startswith('-') else name
			try:
				parser.add_argument(op, name, help=desc, dest=name, default=val, action=act, required=req)
			except argparse.ArgumentError as e:
				self.error(f"ModuleException: {e}")
		# Initialize help menu
		format_help = parser.format_help()
		# comments
		if 'comments' in meta:
			format_help += 'Comments:'
			for comment in meta['comments']:
				prefix = '* '
				if comment.startswith('\t'):
					prefix = self.spacer + '- '
					comment = comment[1:]
				format_help += f"\n{self.spacer}{textwrap.fill(prefix+comment, 100, subsequent_indent=self.spacer)}"
			format_help += '\n'
		if 'sources' in meta:
			format_help += '\nSources:\n\t' + '\n\t'.join(meta['sources'])
		if 'examples' in meta:
			format_help += '\nExamples:\n\t' + '\n\t'.join(meta['examples'])

		# If args is nothing
		if not args:
			print(format_help)
		else:
			# Initialite args
			clean_args = []
			for arg in args.split(' '):
				if arg.startswith('$'):
					arg = self.get_var(arg[1:])
				clean_args.append(arg)
			clean_args = ' '.join(clean_args)

			args = parser.parse_args(shlex.split(clean_args))
			args = vars(args)
			# Set options
			for option in args:
				mod.options[option[2:]] = args[option]

			# Run the tool
			spool_flag = 0
			try:
				if output:
					output = 'start ' + output
					self.do_spool(output)
					spool_flag = 1
				mod._validate_options()
				mod.module_pre()
				mod.module_run()
				mod.module_post()
			except KeyboardInterrupt:
				return
			except Exception:
				self.print_exception()
			finally:
				if spool_flag:
					self.do_spool('stop')

	def run_tool(self, func, tool_name, args, output=None):
		try:
			
			# process(target=func_ref , args=()) => run func_ref(args) in seprate process
			proc = Process(target=getattr(self, func), args=(tool_name, args, output))
			proc.start()
			proc.join()
			# python > 3.7
			if 'kill' in dir(proc):
				proc.kill()
		except KeyboardInterrupt:
			return
		except:
			self.print_exception()

# =================================================
# SUPPORT CLASSES
# =================================================
class Mode(object):
	'''Contains constants that represent the state of the interpreter.'''
	CONSOLE = 0
	CLI = 1
	GUI = 2

	def __init__(self):
		# NotImplementedError to indicate that the real implementation still needs to be added.
		raise NotImplementedError("This class should never be instantiated.")
