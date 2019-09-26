import React from 'react'
import {Icon} from 'rmwc/Icon';


export default class SkBigIcon extends React.Component {
  render() {
    return (
      <div className={"sm-icon-wrap fl-center " + this.props.class}>
        <Icon strategy="ligature" className="sm-icon">{this.props.icon}</Icon>
      </div>
    );
  }
}
