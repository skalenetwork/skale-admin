import React from 'react'
import {Icon} from 'rmwc/Icon';


export default class CardTitle extends React.Component {
  render() {
    return (
      <div className={this.props.className + " fl-cont fl-center-vert card-top"}>
        <div className="fl-col padd-ri-10">

            <div className={this.props.color+'-icon' + " md-icon-wrap fl-center"}>
                  <Icon strategy="ligature" className="sm-icon">{this.props.icon}</Icon>
                </div>

        </div>
        <div className="fl-col">
          <h5 className="bold no-marg card-title">{this.props.text}</h5>
        </div>
      </div>
    );
  }
}

CardTitle.defaultProps = {
  color: 'card-title'
};