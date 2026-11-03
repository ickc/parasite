# para.site's documentation, built with para.site (pandoc, and para with its search extra)

.PHONY: docs serve clean
docs: pages/reference.md
	parasite

# every key, from para.site's own defaults
pages/reference.md: ../src/para/defaults.toml
	python -c 'import sys; src = open(sys.argv[1]).read(); open(sys.argv[2], "w").write("---\ntitle: Every key\ndescription: para.site\x27s defaults.toml, which a site\x27s parasite.toml is merged over.\n---\n\n<!-- written by docs/makefile from src/para/defaults.toml: do not edit -->\n\nA site\x27s `parasite.toml` is merged over this file (see [parasite.toml](../configuration/)).\n\n```toml\n" + src + "```\n")' $< $@

serve: docs
	python -m http.server --directory output 8000

clean:
	rm -rf output .para
