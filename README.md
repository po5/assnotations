# assnotations
High fidelity renderer for YouTube XML annotations in .ass format

## Usage
assnotations.py takes in a filename for XML annotations, and writes the converted ass script to stdout.  
Script dimensions can be defined with `--width` and `--height`.

Not all annotation features are supported yet, but this should render most annotations accurately.  
Support for more output formats (vtt, srt) is planned in the future.

## Acknowledgements

[AnnotationsRestored](https://github.com/afrmtbl/AnnotationsRestored) team for help with implementation details, including the speech_bubble function which is ported from their code.
