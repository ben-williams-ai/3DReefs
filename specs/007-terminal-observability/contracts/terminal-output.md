# Contract: Terminal Output

## Stage Messages

Interactive runs must emit plain text messages in this shape:

```text
[stage-name] started
[stage-name] complete in 12.34s
[stage-name] failed: reason
```

Additional context may follow the stage name, for example selected patch counts or output paths.

## External Tool Output

Lines produced by COLMAP, LFS, and splat-transform must be written to:

- the terminal stdout/stderr stream visible to the user
- the existing stage-specific log file

The pipeline must not require users to run `tail -f` to see normal tool progress.
