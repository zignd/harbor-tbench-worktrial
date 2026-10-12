import sys
import os

def write(path, content):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    print(f'wrote {path}')

if len(sys.argv) < 3:
    print(f'Usage: {sys.argv[0]} <repo_dir> <stage>', file=sys.stderr)
    sys.exit(1)

repo = sys.argv[1]
mode = sys.argv[2]
os.chdir(repo)

LIB_RS = '''
pub mod codec;
pub mod frame;

pub use codec::{encode_packet, decode_packet};
'''

MAIN_RS = '''
fn main() {
    println!("packet-codec service");
}
'''

