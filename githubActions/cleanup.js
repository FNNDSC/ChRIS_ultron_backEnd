const child_process = require('child_process');

child_process.execFileSync(
  'just', ['nuke']
  { stdio: 'inherit' }
);
