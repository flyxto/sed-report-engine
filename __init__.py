"""Portal adapter for the client's reporting packages.

`reporting` draws an element PDF. `sed_reporting` turns a project file into
the SCR, PS1, SIR, RFI and PS4. This package is the piece between them and
the sed.works portal: it reshapes the project the Node backend already
stores into the project file those packages validate, then generates the
preview or the PDF.
"""

__version__ = "0.1.0"
