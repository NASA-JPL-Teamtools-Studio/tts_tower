# Tower

![Project logo](https://github.com/NASA-JPL-Teamtools-Studio/teamtools_documentation/blob/main/docs/images/tts_image_artifacts/tower.png)

## About Teamtools Studio

Teamtools Studio Utilities is part of JPL's Teamtools Studio (TTS).

TTS is an effort originated in JPL's Planning and Execution section to centralize shared repositories across missions. This benefits JPL by reducing cost through reducing duplicated code, collaborating across missions, and unifying standards for development and design across JPL.

Although Planning and Execution is primarily concerned with flight operations, the TTS suite has been generalized and atomized to the point where many of these tools are applicable during other mission phases and even in non-spaceflight contexts. Through our work flying space missions, we hope to provide tools to the open source community that have utility in data analysis or planning for any complex system where failure is not an option.

For more infomation on how to contribute, and how these libraries form a complete ecosystem for high reliability data analysis, see the [Full TTS Documentation](https://nasa-jpl-teamtools-studio.github.io/teamtools_documentation/).


### Overview
Tower is a Python infrastructure for implementing automated Rule-based checks from varied input sources in an ops-like environment. It was originally written for M20 and MSL operations, and has since been taken to Europa Clipper and OCO-2. Although it was originally written in the context of Flight Rule checking, it could be generalized to any rule checking, especially if there is a clear dictionary of rules that need to be checked. Rules can be checked directly in Tower, or it can be used to consume the output of upstream tools like SeqGen, FRESH, or SSIM. In the case where these tools are Pyhton-based, they can be called as libraries at runtime within Tower. This allows the Tower developer to combine outputs of upstream tools in arbitrary ways in order to best check the spirit of what they are intended to check, and removes the tedious task of manually comparing outputs of tools with disparate reporting styles.

Although it may feel like Tower can or should also be used for downlink assessment, that is not what it is meant for. For the very similar function of autodispositioning in downlink analysis, see Dexter.


### Inputs, Checks, Dispositions, and Reports.
Tower's basic construction is in 3 layers.

#### Input Layer: 
The input layer is a series of Python classes (called Input Clients), each representing some input into planning. Input Clients are essentially data containers holding the information against which we will do our tests. They are implemented via Abstract Base Classes and provide patterns for the developer to follow that will enable a clear and concise interface to the Checker and Reporting layers while still providing powerful customizability. Inputs into the input layer may be the outputs of upstream tools (Sequences, JSON, CSV, etc), Rule Dictionaries, or basic statistics about the plan (predicted uplink time, sol number, venue, etc). For more complex data, Input Clients can also take other Input Clients as their inputs.

#### Checker Layer: 
The checker layer is where rules are checked. Each checker can take any number of input clients as inputs. As the checker inspects its clients, it adds _dispositions_ to rule results. Dispositions are the result of an atomic check, and can be PASSED, FLAGGED, VIOLATED, or INFO_ONLY.

#### Rule Result Layer (and dispostions):
 The RuleResults class is meant to marry the dispositions defined in the Checker layer with the rule dictionary items they represent. Each RuleResult object as an associated status, which is the roll up of the statuses of its dispositions. (e.g. if a rule has 3 dispoisitions of PASSED, PASSED, and FLAGGED status, then the rule will have a FLAGGED status)

### Elegant Error Handling
Failsafety is one of Tower's most important design principles. It was developed with teamtools developers in mind, who often need to write critical code, but for the various reasons that teamtools exist, are often not the best coders at JPL.

Tower's answer to this is to wrap all Input Clients and Checkers into Input Management and Checker Management layers respectively. Each input and each checker runs in isolation wrapped in a try/except block. If any client or checker fails to run correctly, it is replaced with a dummy object that will allow downstream tools expecting to consume its output to still run to completion. If any part of a check fails, Tower will _still report the results of the part that didn't_ while highlighting the check as needing human intervention. This will mean debugging the failure, or if the operator is not comfortable traversing Tower code, understanding what needs to be done in order to complete the check manually. Tower's use of native rule dictionaries also enforces that the final reports will never hide a rule from the operator just because its implementation failed.

This allows spacecraft planning to proceed, even if there is a bug in the code and no developer is available to fix it. It may mean more manual work on the part of the operator, but Tower is explicitly designed to minimize the work needed to plan given the limitations of any particular rule check, even a complete failure.

### Unit Testing Framework
Tower and its mission-specific implementations also create strong patterns for how to generate unit tests to ensure that all check code is healthy under known conditions. This is also pivotal to the distributed nature of the tool and its management under the Teamtools Studio. The basic pattern is that every input client and every checker should have at least one test. Input client tests should protect against all known ways an input could be malformed, and checker tests should check at least one exemplar of a test passing and failing in its unit tests.

### Reporting
Another powerful feature of Tower is its reporting interface. The primary reporting interface features a list of all rules in the dicitonary (whether they were checked or not). Results are presented so the most severe violations bubble to the top, and filtering and sorting of the main table is provided out of the box, and each row is clickable to show extended metadata from the rule defintion (customizable on a per-mission implementation) and the results of each discrete disposition that was added to the RuleResult object

When defining a checker code, it is also possible to attach arbitrary HTML code to a rule as a besopoke report. Those show up in the top ribbon of the Tower output and also in line with their rules in the main table. Multiple RuleResult objects can contribute to each report, and contributing rule resultes are rolled up at the top of each.

### Projects Currently Supported

* Eurpa Clipper
* Mars 2020/Perseverance
* Mars Science Laboratory/Curiosity
* Orbiting Carbon Observatory 2 (OCO-2)

## Architecture

### TTS dependencies

* TTS Utilities
* HTML Utilities
