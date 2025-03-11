# iClicker


To Setup the Virtual Environment:
1. Create and activate the virtual environment:
```python -m venv venv```
```source venv/bin/activate```

2. Then, select the correct interpreter to run with the play button in VS Code.
    1. Open your project folder in VS Code.
    2. Open the Command Palette by pressing Ctrl+Shift+P (Cmd+Shift+P on Mac).
    3. Type and select Python: Select Interpreter.
    4. From the list, choose the Python interpreter located in your project’s virtual environment folder. It usually has a path like ./venv/bin/python or ./venv/Scripts/python depending on your OS.
3. Run with play button or python3 iclicker_to_csv.


To setup the environment variables containing your email and password:
1. Create a .env file
2. In the .env file: 

    ```ICLICKER_USERNAME=""```

    ```ICLICKER_PASSWORD=""```

3. The variables will be loaded correctly into the iclicker_to_csv file and can now run.