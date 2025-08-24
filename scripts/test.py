# %%
import atexit


@atexit.register
def end() -> None:
    print("End of script")


print("hello world")
