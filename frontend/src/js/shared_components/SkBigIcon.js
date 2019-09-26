import React from 'react'
import {Icon} from 'rmwc/Icon';


export default class SkMdIcon extends React.Component {
  render() {
    return (
      <div className={"md-icon-wrap fl-center " + this.props.class}>
        <Icon strategy="ligature" className="sm-icon">{this.props.icon}</Icon>
      </div>
    );
  }
}
