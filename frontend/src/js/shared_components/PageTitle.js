import React from 'react'
export default class PageTitle extends React.Component {
  render() {
    return (
      <div className={"page-title " + (this.props.nopadd ? '' : 'padd-bott-md')}>
        <h3 className="no-marg page-title">
          {this.props.title}
        </h3>
        {(this.props.subtitle) ? (<h6 className="page-desc marg-top-sm">
          {this.props.subtitle}
        </h6>) : undefined}
      </div>
    );
  }
}
