"""A city built by many agents at once (docs/ghost/city.md): the multi-agent harness on Temporal.

One orchestrating workflow plans the city with one macro planner, fans the districts out to parallel
district planners, checks and repairs the merged layout, lays the roads and terraces with code, then
fans the plots out to parallel builder agents (a sliding window of N), each judged by an audit and a
critic, with one fix round when it falls short. Every agent's tools are scoped to its own files; every
step is stored; a killed worker resumes where it stopped."""
