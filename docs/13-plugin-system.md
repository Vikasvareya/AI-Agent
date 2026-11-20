# Plugin System

The plugin interface can provide planner intents and tools. The plugin loader
discovers/imports Python modules; a math plugin is included. This is a basic
extension seam, not a marketplace or secure plugin platform.

Importing a plugin executes Python in the framework process. There is no
plugin sandbox, signature verification, dependency isolation, versioned
manifest, or coding-agent plugin invocation. Only install and load code that
the operator trusts.

Governed plugin installation and execution are proposed in the
[Product Roadmap](./PRODUCT_ROADMAP.md), not current functionality.
