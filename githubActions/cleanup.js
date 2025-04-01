const child_process = require('child_process');
const path = require('path');

child_process.execFileSync(
  'just', ['nuke'],
  {
    stdio: 'inherit',
    cwd: path.resolve(__dirname, '..')
  }
);
