# The project's targets are in the Makefile at the repository root, where the judges run
# `make run`. This one passes every target on to it, so `make run` works from here too.
# Variables given on the command line (`make run OPEN_BROWSER=0`) are passed on as well.
.PHONY: run
run:
	@$(MAKE) --no-print-directory -C .. run

# Keeps make from trying to remake this file through the rule below.
Makefile: ;

%:
	@$(MAKE) --no-print-directory -C .. $@
