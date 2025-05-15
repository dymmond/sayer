import importlib.metadata


def load_plugins():
    for entry_point in importlib.metadata.entry_points().get("sayer.commands", []):
        try:
            register_func = entry_point.load()
            register_func()
        except Exception as e:
            print(f"[Plugin Load Failed] {entry_point.name}: {e}")
