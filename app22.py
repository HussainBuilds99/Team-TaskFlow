"""Team TaskFlow - Streamlit entry point.

The application itself lives in the ``taskflow`` package; this file stays at the
repository root because it is the script Streamlit Community Cloud is
configured to run.

    streamlit run app22.py
"""

from taskflow.app import main

if __name__ == "__main__":
    main()
