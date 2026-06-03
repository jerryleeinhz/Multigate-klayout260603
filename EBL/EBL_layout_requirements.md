# EBL layout requirements

- Preserve the existing base layout structure unless a geometry change is explicitly requested.
- Change only the requested working-area placement, electrode widths, gaps, equal-length center geometry, and gap markers.
- Do not allow marker geometries and routing/metal traces to overlap.
- For shared wire-bond electrodes, keep the existing outside pad count and keep one shared pad between each pair of adjacent working areas.
- In each four-radial working area, distribute the 8 center electrodes uniformly around the circular center and route them to pads with smooth, tangent-continuous curves instead of sharp bends.
