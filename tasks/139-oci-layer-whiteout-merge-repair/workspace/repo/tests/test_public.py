import unittest
from src.layer_merge import merge_layers

def entry(path,kind="file",digest="sha256:x",target=None,mode=420):
    return {"path":path,"kind":kind,"digest":digest if kind=="file" else None,"target":target,"mode":mode}

class LayerTests(unittest.TestCase):
    def test_opaque_keeps_same_layer_addition(self):
        layers=[{"digest":"b","entries":[entry("a", "dir", None, None,493),entry("a/old")]},{"digest":"n","entries":[entry("a/new"),entry("a/.wh..wh..opq",digest="sha256:empty",mode=0)]}]
        paths=[row["path"] for row in merge_layers(layers,{"implicit_dir_mode":493})["rootfs"]]
        self.assertIn("a/new",paths); self.assertNotIn("a/old",paths)

    def test_file_replacement_drops_descendants(self):
        layers=[{"digest":"b","entries":[entry("a", "dir", None, None,493),entry("a/x")]},{"digest":"n","entries":[entry("a")]}]
        self.assertEqual([row["path"] for row in merge_layers(layers,{"implicit_dir_mode":493})["rootfs"]],["a"])

if __name__=="__main__": unittest.main()
