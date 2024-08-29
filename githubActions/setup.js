const child_process = require('child_process');

child_process.execFileSync(
  'sudo',
  ['apt-get', 'install', '-y', 'just'],
  { stdio: 'inherit' }
);
