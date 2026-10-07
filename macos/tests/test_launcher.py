import os,subprocess,tempfile,unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/'start-rsat.sh'
class LauncherTests(unittest.TestCase):
 def run_case(self,cold=False,failure=False):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);project=base/'project';project.mkdir()
   (project/'.env').write_text('TEST=1');(project/'docker-compose.yml').write_text('services: {}')
   bins=base/'bin';bins.mkdir();state=base/'ready';calls=base/'calls'
   if not cold:state.touch()
   files={
    'docker':f'''#!/bin/bash
if [[ "$*" == *" info" ]]; then [[ -f '{state}' ]]; exit $?; fi
printf '%s\\n' "$*" >> '{calls}'
exit {1 if failure else 0}
''',
    'colima':f'''#!/bin/bash
printf '%s\\n' "colima $*" >> '{calls}'
touch '{state}'
''',
    'curl':'#!/bin/bash\nexit 0\n',
   }
   for name,body in files.items():
    p=bins/name;p.write_text(body);p.chmod(0o700)
   env=os.environ.copy();env['RSAT_LAUNCHER_TEST_BIN']=str(bins)
   result=subprocess.run(['/bin/bash',str(SCRIPT),str(project)],env=env,capture_output=True,text=True,timeout=10)
   return result,calls.read_text() if calls.exists() else ''
 def test_cold_start_preserves_profile_and_never_rebuilds_or_pulls(self):
  result,calls=self.run_case(cold=True)
  self.assertEqual(result.returncode,0)
  self.assertIn('colima start default --activate=false',calls)
  self.assertIn('--project-name rsat-full-for-macos-linux',calls)
  self.assertIn('--no-build --pull never --wait',calls)
  self.assertNotIn('delete',calls);self.assertNotIn('down',calls)
 def test_running_engine_is_reused(self):
  result,calls=self.run_case()
  self.assertEqual(result.returncode,0)
  self.assertNotIn('colima start',calls)
 def test_failed_services_do_not_report_success(self):
  result,calls=self.run_case(failure=True)
  self.assertNotEqual(result.returncode,0)
  self.assertNotIn('RSAT READY',result.stdout)
 def test_missing_project_is_explicit(self):
  result=subprocess.run(['/bin/bash',str(SCRIPT),'/nonexistent-rsat-project'],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0)
unittest.main()
