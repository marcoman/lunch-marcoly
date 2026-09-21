# 61-reference

Python web baseline for the observability series.

It preserves the [00-reference-code behavior](../../00-reference-code/application.md),
but moves login, navigation, and logout state from browser JavaScript into
Python HTTP endpoints. This gives `62-server-traces` meaningful server
operations to trace without mixing an architecture rewrite into the
observability lesson.

There is **no LaunchDarkly integration** in this example.

## First-time run

1. Install Python **3.12+**. The repository uses
   [pyenv](https://github.com/pyenv/pyenv) and a shared virtual environment.
2. From the repository root:

   ```bash
   pyenv install 3.12
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Start the application:

   ```bash
   cd 60-observability/61-reference/python
   python 61-reference.py
   ```

4. Open [http://127.0.0.1:8610/](http://127.0.0.1:8610/).
5. Enter a username and navigate with arrow keys or WASD. Press `L` to log out
   and `Q` to close the application view.

See [application.md](application.md) for the endpoint and state contract.
