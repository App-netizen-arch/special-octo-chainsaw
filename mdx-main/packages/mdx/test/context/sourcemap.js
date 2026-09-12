import {jsx as _jsx} from "react/jsx-runtime";
export function Component() {
  a();
}
function _createMdxContent(props) {
  return _jsx(Component, {});
}
export default function MDXContent(props = {}) {
  const {wrapper: MDXLayout} = props.components || ({});
  return MDXLayout ? _jsx(MDXLayout, {
    ...props,
    children: _jsx(_createMdxContent, {
      ...props
    })
  }) : _createMdxContent(props);
}

//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbInVua25vd24uanMiXSwibmFtZXMiOlsiYSJdLCJtYXBwaW5ncyI6IjtPQUFPO0VBQ0xBIiwiZmlsZSI6InVua25vd24uanMifQ==
